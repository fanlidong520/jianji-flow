from __future__ import annotations

import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Callable


_PTS_TIME_RE = re.compile(r"pts_time:\s*(-?\d+(?:\.\d+)?)")
BoundaryDetector = Callable[[Path, int, int], list[int]]


def _scene_command(video_path: Path, start_ms: int, duration_ms: int, threshold: float) -> list[str]:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    filter_text = f"select='gt(scene\\,{threshold:.3f})',showinfo"
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "info",
        "-nostdin",
        "-ss",
        f"{start_ms / 1000:.3f}",
        "-t",
        f"{duration_ms / 1000:.3f}",
        "-i",
        str(video_path),
        "-vf",
        filter_text,
        "-an",
        "-f",
        "null",
        "-",
    ]


def detect_scene_boundaries(
    video_path: Path,
    start_ms: int,
    end_ms: int,
    *,
    threshold: float = 0.25,
    min_shot_ms: int = 900,
    max_shots: int = 4,
) -> list[int]:
    """Return safe absolute source boundaries, including start and end."""
    if start_ms < 0 or end_ms <= start_ms:
        raise ValueError("source range must be positive")
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be between 0 and 1")
    if min_shot_ms <= 0:
        raise ValueError("min_shot_ms must be positive")
    if max_shots < 2:
        raise ValueError("max_shots must be at least 2")

    duration_ms = end_ms - start_ms
    if duration_ms < min_shot_ms * 2:
        return [start_ms, end_ms]

    result = subprocess.run(
        _scene_command(video_path, start_ms, duration_ms, threshold),
        check=False,
        shell=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "scene detection failed"
        raise RuntimeError(detail)

    candidates = [start_ms + round(float(value) * 1000) for value in _PTS_TIME_RE.findall(result.stderr)]
    candidates = sorted({value for value in candidates if start_ms + min_shot_ms <= value <= end_ms - min_shot_ms})
    selected = [start_ms]
    for boundary in candidates:
        if boundary - selected[-1] < min_shot_ms:
            continue
        if end_ms - boundary < min_shot_ms:
            continue
        selected.append(boundary)
        if len(selected) >= max_shots:
            break
    selected.append(end_ms)
    return selected


def build_multi_shot_matches(
    segments: list[dict],
    matches: dict,
    *,
    detector: BoundaryDetector = detect_scene_boundaries,
    min_shot_ms: int = 900,
    max_shots: int = 4,
) -> tuple[dict, dict]:
    """Attach bounded structural shot ranges while preserving parent matches."""
    segment_by_id = {str(segment.get("id")): segment for segment in segments}
    updated_matches: list[dict] = []
    plan_segments: list[dict] = []
    total_shots = 0
    warnings: list[str] = []

    for original in matches.get("matches", []):
        match = dict(original)
        segment_id = str(match.get("segment_id", ""))
        segment = segment_by_id.get(segment_id)
        if segment is None or match.get("status") not in {"selected", "low_confidence"}:
            updated_matches.append(match)
            continue

        start_ms = int(match["source_start_ms"])
        end_ms = int(match["source_end_ms"])
        try:
            boundaries = detector(Path(str(match["source_path"])), start_ms, end_ms)
        except (OSError, RuntimeError, ValueError) as exc:
            boundaries = [start_ms, end_ms]
            warnings.append(f"{segment_id}: multi-shot detection fell back to one source window: {exc}")

        ranges = list(zip(boundaries, boundaries[1:]))
        if len(ranges) <= 1:
            warnings.append(f"{segment_id}: no safe internal scene boundary; kept one source window")
            plan_segments.append({"segment_id": segment_id, "shot_count": 1, "status": "fallback"})
            updated_matches.append(match)
            total_shots += 1
            continue

        shots = []
        for index, (shot_start_ms, shot_end_ms) in enumerate(ranges, start=1):
            shots.append(
                {
                    "shot_id": f"{segment_id}-shot-{index:02d}",
                    "asset_id": str(match["asset_id"]),
                    "source_path": str(match["source_path"]),
                    "source_start_ms": int(shot_start_ms),
                    "source_end_ms": int(shot_end_ms),
                    "asset_duration_ms": int(match["asset_duration_ms"]),
                    "evidence": ["scene-change-boundary"],
                }
            )
        match["shots"] = shots
        evidence = [item for item in match.get("evidence", []) if not str(item).startswith("multi-shot:")]
        evidence.append(f"multi-shot:{len(shots)}")
        match["evidence"] = evidence
        plan_segments.append(
            {
                "segment_id": segment_id,
                "shot_count": len(shots),
                "status": "detected",
                "boundaries_ms": boundaries,
            }
        )
        total_shots += len(shots)
        updated_matches.append(match)

    plan = {
        "version": "0.1",
        "status": "warning" if warnings else "pass",
        "total_shots": total_shots,
        "segments": plan_segments,
        "warnings": warnings,
        "limits": {"min_shot_ms": min_shot_ms, "max_shots": max_shots},
    }
    return {**matches, "matches": updated_matches}, plan


def synchronize_shot_plan(plan: dict, matches: dict) -> dict:
    """Refresh audit boundaries after the final timeline retime."""
    refreshed = deepcopy(plan)
    matches_by_segment = {
        str(match.get("segment_id")): match for match in matches.get("matches", [])
    }
    total_shots = 0
    for item in refreshed.get("segments", []):
        match = matches_by_segment.get(str(item.get("segment_id")))
        shots = match.get("shots", []) if match else []
        if shots:
            item["shot_count"] = len(shots)
            item["status"] = "detected"
            item["boundaries_ms"] = [
                int(shots[0]["source_start_ms"]),
                *[int(shot["source_end_ms"]) for shot in shots],
            ]
        else:
            item["shot_count"] = 1
            item["status"] = "fallback"
            item.pop("boundaries_ms", None)
        total_shots += int(item.get("shot_count", 0))
    refreshed["total_shots"] = total_shots
    return refreshed
