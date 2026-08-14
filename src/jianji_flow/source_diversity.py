from __future__ import annotations

import shutil
from pathlib import Path

from .visual_similarity import mean_frame_difference


def _value(asset: dict, name: str, default=0):
    return asset.get(name, default)


def _duration_ms(asset: dict) -> int:
    try:
        return int(_value(asset, "duration_ms"))
    except (TypeError, ValueError):
        return 0


def _is_candidate(left: dict, right: dict, *, duration_tolerance_ms: int) -> bool:
    left_path = str(_value(left, "path", "")).strip()
    right_path = str(_value(right, "path", "")).strip()
    if not left_path or not right_path:
        return False

    left_hash = str(_value(left, "sha256", "")).strip().casefold()
    right_hash = str(_value(right, "sha256", "")).strip().casefold()
    if left_hash and right_hash and left_hash == right_hash:
        return False

    left_width = int(_value(left, "width", 0) or 0)
    left_height = int(_value(left, "height", 0) or 0)
    right_width = int(_value(right, "width", 0) or 0)
    right_height = int(_value(right, "height", 0) or 0)
    if (left_width, left_height) != (right_width, right_height):
        return False

    left_duration = _duration_ms(left)
    right_duration = _duration_ms(right)
    if left_duration <= 0 or right_duration <= 0:
        return False
    tolerance = max(duration_tolerance_ms, round(min(left_duration, right_duration) * 0.05))
    return abs(left_duration - right_duration) <= tolerance


def diagnose_source_diversity(
    assets: list[dict],
    diagnostics_dir: Path,
    *,
    threshold: float = 3.0,
    duration_tolerance_ms: int = 250,
) -> dict:
    similar_groups: list[dict] = []
    warnings: list[str] = []
    pair_index = 0

    for left_index, left in enumerate(assets):
        for right in assets[left_index + 1 :]:
            if not _is_candidate(left, right, duration_tolerance_ms=duration_tolerance_ms):
                continue

            pair_index += 1
            pair_dir = diagnostics_dir / f"pair-{pair_index:03d}"
            left_path = Path(str(left["path"]))
            right_path = Path(str(right["path"]))
            try:
                score = mean_frame_difference(
                    left_path,
                    right_path,
                    duration_ms=min(_duration_ms(left), _duration_ms(right)),
                    diagnostics_dir=pair_dir,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                warnings.append(
                    f"Could not compare {left_path.name} and {right_path.name} for source diversity: {exc}"
                )
                continue

            if score <= threshold:
                similar_groups.append(
                    {
                        "paths": [left_path.as_posix(), right_path.as_posix()],
                        "score": round(float(score), 3),
                    }
                )
            elif pair_dir.exists():
                shutil.rmtree(pair_dir)

    if not similar_groups and not warnings and diagnostics_dir.exists():
        shutil.rmtree(diagnostics_dir)

    return {
        "status": "warning" if similar_groups or warnings else "pass",
        "similar_groups": similar_groups,
        "warnings": warnings,
        "diagnostics_dir": diagnostics_dir.as_posix(),
    }
