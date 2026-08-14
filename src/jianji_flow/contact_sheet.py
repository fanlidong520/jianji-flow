from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

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


def build_shot_frame_times_ms(recipe: dict, matches: dict) -> list[tuple[str, int]]:
    """Return final-timeline midpoint samples for every rendered shot."""
    matches_by_id = {str(match.get("id")): match for match in matches.get("matches", [])}
    samples: list[tuple[str, int]] = []
    for segment in recipe.get("segments", []):
        match = matches_by_id.get(str(segment.get("match_id")))
        if match is None:
            raise ValueError(f"segment {segment.get('id')!r}: match is missing")
        segment_id = str(segment.get("id", "segment"))
        shots = match.get("shots")
        playback_rate = float(match.get("playback_rate", 1.0))
        if playback_rate <= 0:
            raise ValueError(f"{segment_id}: playback_rate must be positive")
        if shots:
            cursor_ms = int(segment["start_ms"])
            segment_end_ms = int(segment["end_ms"])
            for index, shot in enumerate(shots, start=1):
                source_duration_ms = int(shot["source_end_ms"]) - int(shot["source_start_ms"])
                if source_duration_ms <= 0:
                    raise ValueError(f"{segment_id} shot {index}: source range must be positive")
                duration_ms = (
                    segment_end_ms - cursor_ms
                    if index == len(shots)
                    else round(source_duration_ms / playback_rate)
                )
                if duration_ms <= 0:
                    raise ValueError(f"{segment_id} shot {index}: timeline range must be positive")
                samples.append((f"{segment_id} / shot-{index:02d}", cursor_ms + round(duration_ms / 2)))
                cursor_ms += duration_ms
        else:
            start_ms = int(segment["start_ms"])
            end_ms = int(segment["end_ms"])
            if end_ms <= start_ms:
                raise ValueError(f"{segment_id}: segment range must be positive")
            samples.append((f"{segment_id} / shot-01", round((start_ms + end_ms) / 2)))
    if not samples:
        raise ValueError("recipe has no segments")
    return samples


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


def _write_labeled_tiled_images(
    frame_paths: list[Path],
    labels: list[str],
    output_path: Path,
    *,
    tile_width: int = 220,
    columns: int = 4,
    padding: int = 8,
    label_height: int = 28,
) -> None:
    if len(frame_paths) != len(labels) or not frame_paths:
        raise ValueError("frame paths and labels must be non-empty and have equal length")
    images = []
    try:
        for frame_path in frame_paths:
            image = Image.open(frame_path).convert("RGB")
            ratio = tile_width / image.width
            images.append(image.resize((tile_width, max(1, round(image.height * ratio)))))
        tile_height = max(image.height for image in images)
        rows = (len(images) + columns - 1) // columns
        sheet_width = padding + columns * (tile_width + padding)
        sheet_height = padding + rows * (label_height + tile_height + padding)
        sheet = Image.new("RGB", (sheet_width, sheet_height), "#202124")
        draw = ImageDraw.Draw(sheet)
        for index, (image, label) in enumerate(zip(images, labels)):
            row, column = divmod(index, columns)
            left = padding + column * (tile_width + padding)
            top = padding + row * (label_height + tile_height + padding)
            draw.text((left, top + 6), label, fill="white")
            sheet.paste(image, (left, top + label_height))
        sheet.save(output_path)
        sheet.close()
    finally:
        for image in images:
            image.close()


def write_shot_contact_sheet(
    video_path: Path,
    output_path: Path,
    *,
    recipe: dict,
    matches: dict,
) -> Path:
    """Write one labeled frame for every final rendered shot."""
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    samples = build_shot_frame_times_ms(recipe, matches)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_path.with_name(f".{output_path.stem}.frames")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    try:
        frame_paths = []
        labels = []
        for index, (label, time_ms) in enumerate(samples, start=1):
            frame_path = temp_dir / f"shot-{index:03d}.png"
            _extract_frame(ffmpeg, video_path, frame_path, time_ms)
            frame_paths.append(frame_path)
            labels.append(label)
        _write_labeled_tiled_images(frame_paths, labels, output_path)
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"shot contact sheet was not created: {output_path}")
    return output_path


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


def write_reference_comparison_sheet(
    reference_path: Path,
    remix_path: Path,
    output_path: Path,
    *,
    recipe: dict,
) -> Path:
    """Write the same number of storyboard samples for the reference and remix."""
    times = build_segment_frame_times_ms(recipe)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_path.with_name(f".{output_path.stem}.frames")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    try:
        row_images: list[Image.Image] = []
        for row_name, video_path in (("reference", reference_path), ("remix", remix_path)):
            row_path = temp_dir / f"{row_name}.png"
            write_contact_sheet(video_path, row_path, frames=len(times))
            row_images.append(Image.open(row_path).convert("RGB"))

        tile_width = 220
        tile_padding = 8
        tile_height = max(1, row_images[0].height - 2 * tile_padding)
        padding = 8
        label_width = 86
        label_height = 28
        row_height = label_height + tile_height + padding
        sheet = Image.new(
            "RGB",
            (
                padding + label_width + len(times) * (tile_width + tile_padding),
                padding + 2 * row_height,
            ),
            "#202124",
        )
        draw = ImageDraw.Draw(sheet)
        for row_index, (row_name, row_image) in enumerate(zip(("Reference", "Remix"), row_images)):
            top = padding + row_index * row_height
            draw.text((padding, top + 6), row_name, fill="white")
            for index in range(len(times)):
                left = padding + label_width + index * (tile_width + tile_padding)
                source_left = tile_padding + index * (tile_width + tile_padding)
                tile = row_image.crop(
                    (source_left, tile_padding, source_left + tile_width, tile_padding + tile_height)
                )
                sheet.paste(tile, (left, top + label_height))
                tile.close()
                segment_id = str(recipe.get("segments", [])[index].get("id", f"seg-{index + 1:03d}"))
                draw.text((left + 4, top + 6), segment_id, fill="#d7e3fc")
        sheet.save(output_path)
        sheet.close()
    finally:
        for row_image in row_images:
            row_image.close()
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"reference comparison sheet was not created: {output_path}")
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
