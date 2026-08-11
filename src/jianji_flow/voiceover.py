from __future__ import annotations

import subprocess
from pathlib import Path


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


def validate_voiceover(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.stat().st_size <= 0:
        raise ValueError(f"voiceover file is empty: {path}")


def create_voiceover(recipe: dict, output_path: Path, *, rate: int = 0) -> Path:
    text = build_voiceover_text(recipe)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    escaped_path = str(output_path).replace("'", "''")
    escaped_text = text.replace("'", "''")
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {rate}; "
            f"$s.SetOutputToWaveFile('{escaped_path}'); "
            f"$s.Speak('{escaped_text}'); "
            "$s.Dispose();"
        ),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "local TTS failed"
        raise RuntimeError(detail)
    validate_voiceover(output_path)
    return output_path
