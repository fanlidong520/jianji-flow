from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from jianji_flow.contracts import validate_matches, validate_recipe


def _asset_field(asset: Any, name: str) -> Any:
    if isinstance(asset, dict):
        if name == "asset_id" and "id" in asset and "asset_id" not in asset:
            return asset["id"]
        return asset[name]
    if name == "asset_id" and hasattr(asset, "id") and not hasattr(asset, "asset_id"):
        return getattr(asset, "id")
    return getattr(asset, name)


def _duration(segment: dict) -> int:
    return int(segment["end_ms"]) - int(segment["start_ms"])


def _source_path(asset: Any) -> str:
    path = _asset_field(asset, "path")
    if isinstance(path, Path):
        return path.as_posix()
    return str(path).replace("\\", "/")


def _role_score(role: str, asset: Any) -> tuple[float, list[str]]:
    name = Path(_source_path(asset)).stem.casefold()
    role_text = role.casefold()
    if role_text and role_text in name:
        return 0.92, [f"filename-role:{role}"]
    return 0.55, ["fallback:first-available"]


def _candidate_for(segment: dict, asset: Any) -> dict:
    confidence, evidence = _role_score(str(segment["role"]), asset)
    segment_duration = _duration(segment)
    return {
        "asset_id": str(_asset_field(asset, "asset_id")),
        "source_path": _source_path(asset),
        "source_start_ms": 0,
        "source_end_ms": segment_duration,
        "score": confidence,
        "evidence": evidence,
    }


def _eligible_assets(segment: dict, assets: Iterable[Any]) -> list[Any]:
    needed = _duration(segment)
    return [asset for asset in assets if int(_asset_field(asset, "duration_ms")) >= needed]


def _pick_asset(segment: dict, assets: list[Any], recent_asset_ids: list[str]) -> Any | None:
    eligible = _eligible_assets(segment, assets)
    if not eligible:
        return None

    role_matches = [
        asset
        for asset in eligible
        if str(segment["role"]).casefold() in Path(_source_path(asset)).stem.casefold()
    ]
    candidates = role_matches or eligible

    for asset in candidates:
        asset_id = str(_asset_field(asset, "asset_id"))
        if len(recent_asset_ids) < 2 or recent_asset_ids[-2:] != [asset_id, asset_id]:
            return asset
    return candidates[0]


def match_segments(segments: list[dict], assets: list[Any], threshold: float = 0.6) -> dict:
    matches = []
    recent_asset_ids: list[str] = []
    for index, segment in enumerate(segments, start=1):
        match_id = f"match-{index:03d}"
        asset = _pick_asset(segment, assets, recent_asset_ids)
        if asset is None:
            matches.append(
                {
                    "id": match_id,
                    "segment_id": segment["id"],
                    "status": "missing",
                    "confidence": 0,
                    "scores": {},
                    "candidates": [],
                    "evidence": [],
                    "missing_reason": "no asset with enough duration",
                }
            )
            continue

        candidate = _candidate_for(segment, asset)
        confidence = float(candidate["score"])
        asset_id = str(candidate["asset_id"])
        recent_asset_ids.append(asset_id)
        matches.append(
            {
                "id": match_id,
                "segment_id": segment["id"],
                "status": "selected" if confidence >= threshold else "low_confidence",
                "asset_id": asset_id,
                "source_path": str(candidate["source_path"]),
                "source_start_ms": int(candidate["source_start_ms"]),
                "source_end_ms": int(candidate["source_end_ms"]),
                "confidence": confidence,
                "scores": {"filename": confidence},
                "candidates": [candidate],
                "evidence": list(candidate["evidence"]),
            }
        )

    result = {"version": "0.1", "matches": matches}
    validate_matches(result)
    return result


def build_recipe(
    mode: str,
    target: dict,
    segments: list[dict],
    matches: dict,
    *,
    output_path: Path | None = None,
    audio_strategy: str = "silent-preview",
) -> dict:
    match_ids = [item["id"] for item in matches["matches"]]
    recipe_segments = []
    for index, segment in enumerate(segments):
        recipe_segment = {
            "id": segment["id"],
            "role": segment["role"],
            "start_ms": int(segment["start_ms"]),
            "end_ms": int(segment["end_ms"]),
            "match_id": segment.get("match_id", match_ids[index]),
            "caption": segment.get("caption", ""),
        }
        recipe_segments.append(recipe_segment)

    recipe = {
        "version": "0.1",
        "mode": mode,
        "duration_ms": int(recipe_segments[-1]["end_ms"]) if recipe_segments else 0,
        "target": target,
        "audio_strategy": audio_strategy,
        "segments": recipe_segments,
    }
    if output_path is not None:
        recipe["output_path"] = output_path.as_posix()

    validate_recipe(recipe)
    return recipe
