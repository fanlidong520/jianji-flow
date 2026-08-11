from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from jianji_flow.media_probe import run_ffprobe


def build_frame_times_ms(duration_ms: int, *, frames: int = 5) -> list[int]:
    if duration_ms <= 0:
        raise ValueError("duration_ms must be positive")
    if frames <= 0:
        raise ValueError("frames must be positive")
    return [round(duration_ms * (index + 0.5) / frames) for index in range(frames)]


def write_contact_sheet(video_path: Path, output_path: Path, *, frames: int = 5) -> Path:
    if frames <= 0:
        raise ValueError("frames must be positive")
    info = run_ffprobe(video_path)
    if info.duration_ms <= 0:
        raise ValueError(f"video duration must be positive: {video_path}")

    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    fps = frames / (info.duration_ms / 1000)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps:.6f},scale=220:-1,tile={frames}x1:padding=8:margin=8:color=white",
        "-frames:v",
        "1",
        str(output_path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        detail = result.stderr.strip() or "contact sheet generation failed"
        raise RuntimeError(detail)
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"contact sheet was not created: {output_path}")
    return output_path
