from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image


def score_frame_information(image: Image.Image) -> float:
    gray = image.convert("L").resize((64, 64))
    pixels = gray.load()
    if gray.width < 2 or gray.height < 2:
        return 0.0
    total_delta = 0
    comparisons = 0
    for y in range(gray.height - 1):
        for x in range(gray.width - 1):
            current = int(pixels[x, y])
            total_delta += abs(current - int(pixels[x + 1, y]))
            total_delta += abs(current - int(pixels[x, y + 1]))
            comparisons += 2
    return total_delta / (comparisons * 255)


def _extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-ss",
        f"{time_ms / 1000:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        str(frame_path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        detail = result.stderr.strip() or f"frame extraction failed at {time_ms}ms"
        raise RuntimeError(detail)


def score_source_window(video_path: Path, start_ms: int, end_ms: int, diagnostics_dir: Path) -> float:
    if end_ms <= start_ms:
        raise ValueError("source window end_ms must be greater than start_ms")
    midpoint_ms = round((start_ms + end_ms) / 2)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    frame_path = diagnostics_dir / f"{video_path.stem}-{start_ms}-{end_ms}.png"
    _extract_frame(video_path, frame_path, midpoint_ms)
    with Image.open(frame_path) as image:
        return score_frame_information(image)
