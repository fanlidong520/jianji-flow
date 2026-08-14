from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

FrameDifference = Any


def build_change_report(
    recipe: dict,
    before_matches: dict,
    after_matches: dict,
    *,
    diagnostics_dir: Path,
    frame_difference: FrameDifference | None = None,
) -> dict:
    before_by_segment = _matches_by_segment(before_matches)
    after_by_segment = _matches_by_segment(after_matches)
    changed_segments = []
    unchanged_segments = []
    unaccounted_segments = []

    for segment in recipe.get("segments", []):
        segment_id = str(segment.get("id", ""))
        before = before_by_segment.get(segment_id)
        after = after_by_segment.get(segment_id)
        if not before or not after:
            unaccounted_segments.append(segment_id)
            continue
        if _same_source_window(before, after):
            unchanged_segments.append(segment_id)
            continue
        changed_segments.append(
            _changed_segment_entry(
                segment,
                before,
                after,
                diagnostics_dir,
                frame_difference or _mean_frame_file_difference,
            )
        )

    return {
        "changed_segments": changed_segments,
        "unchanged_segments": unchanged_segments,
        "unaccounted_segments": unaccounted_segments,
    }


def _matches_by_segment(matches: dict) -> dict[str, dict]:
    return {
        str(match.get("segment_id", "")): match
        for match in matches.get("matches", [])
        if isinstance(match, dict)
    }


def _same_source_window(before: dict, after: dict) -> bool:
    return (
        _path_key(before.get("source_path")) == _path_key(after.get("source_path"))
        and before.get("source_start_ms") == after.get("source_start_ms")
        and before.get("source_end_ms") == after.get("source_end_ms")
    )


def _changed_segment_entry(
    segment: dict,
    before: dict,
    after: dict,
    diagnostics_dir: Path,
    frame_difference: FrameDifference,
) -> dict:
    duration_ms = _source_duration_ms(after) or _source_duration_ms(before)
    entry: dict[str, Any] = {
        "segment_id": str(segment.get("id", "")),
        "role": str(segment.get("role", "")),
        "caption": str(segment.get("caption", "")),
        "before_asset": str(before.get("source_path", "")),
        "before_range": _source_range_text(before),
        "before_frame": "",
        "after_asset": str(after.get("source_path", "")),
        "after_range": _source_range_text(after),
        "after_frame": "",
        "visual_difference": None,
        "reason": _change_reason(after),
    }
    try:
        before_frame = diagnostics_dir / f"{_safe_name(str(segment.get('id', 'segment')))}-before.png"
        after_frame = diagnostics_dir / f"{_safe_name(str(segment.get('id', 'segment')))}-after.png"
        offset_ms = round(duration_ms / 2)
        _extract_frame(
            Path(str(before.get("source_path", ""))),
            before_frame,
            _int_value(before.get("source_start_ms"), 0) + offset_ms,
        )
        _extract_frame(
            Path(str(after.get("source_path", ""))),
            after_frame,
            _int_value(after.get("source_start_ms"), 0) + offset_ms,
        )
        entry["before_frame"] = before_frame.as_posix()
        entry["after_frame"] = after_frame.as_posix()
        entry["visual_difference"] = round(
            frame_difference(
                before_frame,
                after_frame,
            ),
            1,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        entry["visual_difference_warning"] = str(exc)
    return entry


def _source_duration_ms(match: dict) -> int:
    start_ms = _int_value(match.get("source_start_ms"), 0)
    end_ms = _int_value(match.get("source_end_ms"), 0)
    return max(0, end_ms - start_ms)


def _source_range_text(match: dict) -> str:
    start_ms = match.get("source_start_ms")
    end_ms = match.get("source_end_ms")
    if isinstance(start_ms, int) and isinstance(end_ms, int):
        return f"{start_ms}-{end_ms}ms"
    return "unknown"


def _change_reason(match: dict) -> str:
    override_evidence = [str(item) for item in match.get("evidence", []) if str(item).startswith("override:")]
    if override_evidence:
        return override_evidence[-1]
    return "source window changed"


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _path_key(value: Any) -> str:
    return str(value or "").replace("\\", "/").casefold()


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
    if not frame_path.exists() or frame_path.stat().st_size <= 0:
        raise RuntimeError(f"frame extraction produced no image at {time_ms}ms")


def _mean_frame_file_difference(before_frame: Path, after_frame: Path) -> float:
    with Image.open(before_frame) as before_image, Image.open(after_frame) as after_image:
        before_rgb = before_image.convert("RGB").resize((64, 64))
        after_rgb = after_image.convert("RGB").resize((64, 64))
        diff = ImageChops.difference(before_rgb, after_rgb)
        return sum(ImageStat.Stat(diff).mean) / 3


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value).strip("-") or "segment"
