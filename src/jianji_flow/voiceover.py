from __future__ import annotations

import base64
import json
import shutil
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


def prepare_voiceover(source_path: Path, output_path: Path, *, timeout_s: int = 60) -> Path:
    """Copy or normalize a local narration file into the pipeline WAV path."""
    source_path = Path(source_path)
    output_path = Path(output_path)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    if source_path.stat().st_size <= 0:
        raise ValueError(f"voiceover file is empty: {source_path}")

    same_file = source_path.resolve() == output_path.resolve()
    if same_file:
        validate_voiceover(source_path)
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    try:
        if source_path.suffix.casefold() in {".wav", ".wave"}:
            shutil.copy2(source_path, output_path)
        else:
            try:
                result = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-v",
                        "error",
                        "-i",
                        str(source_path),
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        "22050",
                        "-c:a",
                        "pcm_s16le",
                        str(output_path),
                    ],
                    check=False,
                    shell=False,
                    timeout=timeout_s,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except FileNotFoundError as exc:
                raise ValueError("FFmpeg is required to convert non-WAV --voiceover audio") from exc
            except subprocess.TimeoutExpired as exc:
                raise ValueError("FFmpeg audio conversion timed out") from exc
            if result.returncode != 0:
                detail = _compact_process_error(result, "voiceover audio conversion failed")
                raise ValueError(f"voiceover audio conversion failed: {detail}")
        validate_voiceover(output_path)
        return output_path
    except Exception:
        if output_path.exists():
            output_path.unlink()
        raise


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
    $s.SelectVoice($voice.VoiceInfo.Name)
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


def _edge_tts_executable() -> str | None:
    return shutil.which("edge-tts") or shutil.which("edge-tts.exe")


def has_edge_tts(timeout_s: int = 10) -> bool:
    executable = _edge_tts_executable()
    if not executable:
        return False
    try:
        result = subprocess.run(
            [executable, "--version"],
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


def _compact_process_error(result: subprocess.CompletedProcess[str], fallback: str) -> str:
    raw = result.stderr.strip() or result.stdout.strip()
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    detail = lines[-1] if lines else fallback
    return detail[-500:]


def create_edge_voiceover(
    recipe: dict,
    output_path: Path,
    *,
    voice: str = "zh-CN-XiaoxiaoNeural",
    timeout_s: int = 60,
) -> Path:
    text = build_voiceover_text(recipe)
    executable = _edge_tts_executable()
    if not executable:
        raise RuntimeError("edge-tts is not installed; install the optional edge-tts dependency or provide --voiceover")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    text_path = output_path.with_name(f".{output_path.stem}.edge-tts.txt")
    media_path = output_path.with_name(f".{output_path.stem}.edge-tts.mp3")
    text_path.write_text(text, encoding="utf-8")
    try:
        tts_result = subprocess.run(
            [executable, "--voice", voice, "--file", str(text_path), "--write-media", str(media_path)],
            check=False,
            timeout=timeout_s,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if tts_result.returncode != 0:
            detail = _compact_process_error(tts_result, "edge TTS failed")
            raise RuntimeError(detail)

        conversion_result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(media_path),
                "-ac",
                "1",
                "-ar",
                "22050",
                str(output_path),
            ],
            check=False,
            timeout=timeout_s,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if conversion_result.returncode != 0:
            detail = _compact_process_error(conversion_result, "edge TTS audio conversion failed")
            raise RuntimeError(detail)
        validate_voiceover(output_path)
        return output_path
    except Exception:
        if output_path.exists():
            output_path.unlink()
        raise
    finally:
        for temporary_path in (text_path, media_path):
            if temporary_path.exists():
                temporary_path.unlink()


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
