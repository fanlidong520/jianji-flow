from __future__ import annotations

from pathlib import Path
from typing import Any

from jianji_flow.asset_diagnosis import primary_role_for_asset


def build_fixes_template(
    recipe: dict,
    matches: dict,
    assets: list[Any],
    review: dict,
    *,
    minimum_duration_recipe: dict | None = None,
) -> dict:
    match_by_id = {str(match.get("id")): match for match in matches.get("matches", [])}
    weak_roles = {str(role).casefold() for role in review.get("story_support", {}).get("weak_evidence_roles", [])}
    duration_by_segment_id = _duration_by_segment_id(minimum_duration_recipe or recipe)
    segments: dict[str, dict] = {}

    for segment in recipe.get("segments", []):
        segment_id = str(segment.get("id", ""))
        role = str(segment.get("role", "")).strip()
        match = match_by_id.get(str(segment.get("match_id")))
        reason = _fix_reason(role, match, weak_roles)
        if reason is None:
            continue

        current_path = _current_source_path(match)
        segments[segment_id] = {
            "role": role,
            "caption": str(segment.get("caption", "")),
            "reason": reason,
            "current_asset_path": current_path,
            "asset_path": "",
            "source_start_ms": None,
            "candidate_asset_paths": _candidate_asset_paths(
                role,
                assets,
                exclude_path=current_path,
                minimum_duration_ms=duration_by_segment_id.get(segment_id, _segment_duration_ms(segment)),
            ),
        }

    return {
        "version": "0.1",
        "how_to_use": "Fill asset_path for any segment you want to replace, then rerun with --fixes fixes.template.json.",
        "segments": segments,
    }


def _duration_by_segment_id(recipe: dict) -> dict[str, int]:
    return {
        str(segment.get("id", "")): _segment_duration_ms(segment)
        for segment in recipe.get("segments", [])
    }


def _fix_reason(role: str, match: dict | None, weak_roles: set[str]) -> str | None:
    if match is None or match.get("status") == "missing":
        return "missing usable asset"
    if match.get("status") == "low_confidence":
        return "low confidence match"
    if role.casefold() in weak_roles:
        return "weak story evidence"
    return None


def _current_source_path(match: dict | None) -> str:
    if not match:
        return ""
    value = match.get("source_path")
    return str(value) if isinstance(value, str) else ""


def _segment_duration_ms(segment: dict) -> int:
    try:
        return max(0, int(segment.get("end_ms", 0)) - int(segment.get("start_ms", 0)))
    except (TypeError, ValueError):
        return 0


def _candidate_asset_paths(role: str, assets: list[Any], *, exclude_path: str, minimum_duration_ms: int) -> list[str]:
    exclude = _path_key(exclude_path)
    role_paths = [
        _asset_path(asset)
        for asset in assets
        if _asset_duration_ms(asset) >= minimum_duration_ms
        and primary_role_for_asset({"path": _asset_path(asset)}) == role
        and _path_key(_asset_path(asset)) != exclude
    ]
    if role_paths:
        return role_paths
    return [
        _asset_path(asset)
        for asset in assets
        if _asset_duration_ms(asset) >= minimum_duration_ms and _path_key(_asset_path(asset)) != exclude
    ]


def _asset_path(asset: Any) -> str:
    path = asset["path"] if isinstance(asset, dict) else getattr(asset, "path")
    if isinstance(path, Path):
        return path.as_posix()
    return str(path).replace("\\", "/")


def _asset_duration_ms(asset: Any) -> int:
    return int(asset["duration_ms"] if isinstance(asset, dict) else getattr(asset, "duration_ms"))


def _path_key(path_text: str) -> str:
    return path_text.replace("\\", "/").casefold()
