from __future__ import annotations

import shutil
import subprocess
from hashlib import sha1
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def mean_frame_difference(
    left_path: Path,
    right_path: Path,
    *,
    duration_ms: int,
    diagnostics_dir: Path,
    left_start_ms: int = 0,
    right_start_ms: int = 0,
) -> float:
    if duration_ms <= 0:
        raise ValueError("duration_ms must be positive")
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    diffs = []
    for index, offset_ms in enumerate(_sample_offsets_ms(duration_ms), start=1):
        left_sample_ms = max(0, int(left_start_ms) + offset_ms)
        right_sample_ms = max(0, int(right_start_ms) + offset_ms)
        left_frame = diagnostics_dir / _frame_name(left_path, "left", index, left_sample_ms)
        right_frame = diagnostics_dir / _frame_name(right_path, "right", index, right_sample_ms)
        _extract_frame_once(left_path, left_frame, left_sample_ms)
        _extract_frame_once(right_path, right_frame, right_sample_ms)
        with Image.open(left_frame) as left, Image.open(right_frame) as right:
            diffs.append(_mean_image_difference(left.convert("RGB"), right.convert("RGB")))
    return sum(diffs) / len(diffs)


def is_visually_similar(
    left_path: Path,
    right_path: Path,
    *,
    duration_ms: int,
    diagnostics_dir: Path,
    threshold: float = 3.0,
    left_start_ms: int = 0,
    right_start_ms: int = 0,
) -> bool:
    return mean_frame_difference(
        left_path,
        right_path,
        duration_ms=duration_ms,
        diagnostics_dir=diagnostics_dir,
        left_start_ms=left_start_ms,
        right_start_ms=right_start_ms,
    ) <= threshold


def _sample_offsets_ms(duration_ms: int) -> list[int]:
    return [max(0, round(duration_ms * fraction)) for fraction in (0.25, 0.5, 0.75)]


def _frame_name(video_path: Path, side: str, index: int, sample_ms: int) -> str:
    identity = sha1(str(video_path.resolve()).encode("utf-8", errors="surrogatepass")).hexdigest()[:10]
    return f"{video_path.stem}-{identity}-similarity-{side}-{index}-{sample_ms}.png"


def _extract_frame_once(video_path: Path, frame_path: Path, time_ms: int) -> None:
    if frame_path.exists() and frame_path.stat().st_size > 0:
        return
    _extract_frame(video_path, frame_path, time_ms)


def _extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
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


def _mean_image_difference(left: Image.Image, right: Image.Image) -> float:
    right_resized = right.resize(left.size)
    diff = ImageChops.difference(left.resize((64, 64)), right_resized.resize((64, 64)))
    return sum(ImageStat.Stat(diff).mean) / 3
