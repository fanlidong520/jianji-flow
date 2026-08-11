from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image

from jianji_flow.media_probe import run_ffprobe


def build_frame_times_ms(duration_ms: int, *, frames: int = 5) -> list[int]:
    if duration_ms <= 0:
        raise ValueError("duration_ms must be positive")
    if frames <= 0:
        raise ValueError("frames must be positive")
    return [round(duration_ms * (index + 0.5) / frames) for index in range(frames)]


def build_segment_frame_times_ms(recipe: dict) -> list[int]:
    times = []
    for segment in recipe.get("segments", []):
        start_ms = int(segment["start_ms"])
        end_ms = int(segment["end_ms"])
        if end_ms <= start_ms:
            raise ValueError("segment end_ms must be greater than start_ms")
        times.append(round((start_ms + end_ms) / 2))
    if not times:
        raise ValueError("recipe has no segments")
    return times


def _extract_frame(ffmpeg: str, video_path: Path, frame_path: Path, time_ms: int) -> None:
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


def _write_tiled_images(frame_paths: list[Path], output_path: Path, *, tile_width: int = 220, padding: int = 8) -> None:
    images = []
    try:
        for frame_path in frame_paths:
            image = Image.open(frame_path).convert("RGB")
            ratio = tile_width / image.width
            images.append(image.resize((tile_width, max(1, round(image.height * ratio)))))
        height = max(image.height for image in images)
        sheet = Image.new("RGB", ((tile_width + padding) * len(images) + padding, height + padding * 2), "white")
        x = padding
        for image in images:
            sheet.paste(image, (x, padding))
            x += tile_width + padding
        sheet.save(output_path)
    finally:
        for image in images:
            image.close()


def _write_segment_contact_sheet(video_path: Path, output_path: Path, recipe: dict) -> Path:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_path.with_name(f".{output_path.stem}.frames")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    try:
        frame_paths = []
        for index, time_ms in enumerate(build_segment_frame_times_ms(recipe), start=1):
            frame_path = temp_dir / f"segment-{index:03d}.png"
            _extract_frame(ffmpeg, video_path, frame_path, time_ms)
            frame_paths.append(frame_path)
        _write_tiled_images(frame_paths, output_path)
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"contact sheet was not created: {output_path}")
    return output_path


def write_contact_sheet(video_path: Path, output_path: Path, *, frames: int = 5, recipe: dict | None = None) -> Path:
    if recipe is not None:
        return _write_segment_contact_sheet(video_path, output_path, recipe)
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
