from __future__ import annotations

import base64
import json
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VoiceoverInfo:
    duration_ms: int


def build_voiceover_text(recipe: dict) -> str:
    captions = [
        str(segment.get("caption", "")).strip()
        for segment in recipe.get("segments", [])
        if str(segment.get("caption", "")).strip()
    ]
    text = "\n".join(captions)
    if not text:
        raise ValueError("voiceover text is empty")
    return text


def _duration_ms_from_payload(payload: dict[str, Any]) -> int:
    format_data = payload.get("format", {})
    duration = format_data.get("duration")
    if duration is None:
        for stream in payload.get("streams", []):
            if isinstance(stream, dict) and stream.get("codec_type") == "audio" and stream.get("duration") is not None:
                duration = stream.get("duration")
                break
    try:
        duration_ms = int(round(float(duration) * 1000))
    except (TypeError, ValueError) as exc:
        raise ValueError("voiceover decode failed: missing duration") from exc
    if duration_ms <= 0:
        raise ValueError("voiceover decode failed: duration is zero")
    return duration_ms


def probe_voiceover(path: Path, timeout_s: int = 30) -> VoiceoverInfo:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.stat().st_size <= 0:
        raise ValueError(f"voiceover file is empty: {path}")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=False,
        shell=False,
        timeout=timeout_s,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "no diagnostic output"
        raise ValueError(f"voiceover decode failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("voiceover decode failed: invalid ffprobe output") from exc
    if not any(isinstance(stream, dict) and stream.get("codec_type") == "audio" for stream in payload.get("streams", [])):
        raise ValueError("voiceover decode failed: no audio stream")
    return VoiceoverInfo(duration_ms=_duration_ms_from_payload(payload))


def _duration_tolerance_ms(duration_ms: int) -> int:
    return 50


def _non_silent_ratio(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            sample_width = handle.getsampwidth()
            total_samples = 0
            audible_samples = 0
            while True:
                chunk = handle.readframes(4096)
                if not chunk:
                    return audible_samples / total_samples if total_samples else 0.0
                if sample_width == 1:
                    total_samples += len(chunk)
                    audible_samples += sum(1 for value in chunk if abs(value - 128) > 1)
                elif sample_width == 2:
                    total_samples += len(chunk) // 2
                    for index in range(0, len(chunk) - 1, 2):
                        if abs(int.from_bytes(chunk[index : index + 2], byteorder="little", signed=True)) > 8:
                            audible_samples += 1
                else:
                    total_samples += len(chunk)
                    audible_samples += sum(1 for value in chunk if value != 0)
    except wave.Error as exc:
        raise ValueError(f"voiceover decode failed: {exc}") from exc


def validate_voiceover(path: Path, *, expected_duration_ms: int | None = None, minimum_duration_ratio: float = 0.6) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.stat().st_size <= 0:
        raise ValueError(f"voiceover file is empty: {path}")
    info = probe_voiceover(path)
    if _non_silent_ratio(path) < 0.01:
        raise ValueError(f"voiceover file is silent: {path}")
    if expected_duration_ms is not None and expected_duration_ms > 0:
        if info.duration_ms < round(expected_duration_ms * minimum_duration_ratio):
            raise ValueError(
                f"voiceover duration {info.duration_ms}ms is too short for recipe {expected_duration_ms}ms"
            )
        if info.duration_ms > expected_duration_ms + _duration_tolerance_ms(expected_duration_ms):
            raise ValueError(
                f"voiceover duration {info.duration_ms}ms exceeds recipe {expected_duration_ms}ms"
            )


def _powershell_single_quoted(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _encoded_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def has_local_chinese_tts(timeout_s: int = 10) -> bool:
    script = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voice = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
    if ($null -eq $voice) { exit 1 }
    exit 0
} finally {
    $s.Dispose()
}
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", _encoded_powershell(script)],
            check=False,
            timeout=timeout_s,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def create_voiceover(recipe: dict, output_path: Path, *, rate: int = 0) -> Path:
    if rate < -10 or rate > 10:
        raise ValueError("rate must be between -10 and 10")
    text = build_voiceover_text(recipe)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    text_path = output_path.with_name(f".{output_path.stem}.tts.txt")
    text_path.write_text(text, encoding="utf-8")
    output_literal = _powershell_single_quoted(str(output_path))
    text_literal = _powershell_single_quoted(str(text_path))
    script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText({text_literal}, [System.Text.Encoding]::UTF8)
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
    $voice = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -eq 'zh-CN' }} | Select-Object -First 1
    if ($null -eq $voice) {{
        throw 'No zh-CN local TTS voice found'
    }}
    $s.SelectVoice($voice.VoiceInfo.Name)
    $s.Rate = {rate}
    $s.SetOutputToWaveFile({output_literal})
    $s.Speak($text)
}} finally {{
    $s.Dispose()
}}
"""
    command = [
        "powershell",
        "-NoProfile",
        "-EncodedCommand",
        _encoded_powershell(script),
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "local TTS failed"
            if output_path.exists():
                output_path.unlink()
            raise RuntimeError(detail)
        validate_voiceover(output_path)
        return output_path
    finally:
        if text_path.exists():
            text_path.unlink()
