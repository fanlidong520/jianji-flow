from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from jianji_flow.contracts import validate_matches, validate_recipe
from jianji_flow.asset_diagnosis import primary_role_for_asset


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


def _asset_duration_ms(asset: Any) -> int:
    return int(_asset_field(asset, "duration_ms"))


WindowScorer = Callable[[Any, int, int], float]


def _window_candidates(segment: dict, asset: Any) -> list[tuple[int, int]]:
    segment_duration = _duration(segment)
    asset_duration = _asset_duration_ms(asset)
    available_offset = max(0, asset_duration - segment_duration)
    starts = {0, available_offset}
    anchor_start = _timeline_source_start_ms(segment, available_offset)
    starts.add(anchor_start)
    starts.add(round(available_offset * 0.5))
    return [(start_ms, start_ms + segment_duration) for start_ms in sorted(starts)]


def _timeline_source_start_ms(segment: dict, available_offset: int) -> int:
    timeline_start = max(0, int(segment.get("start_ms", 0)))
    segment_duration = _duration(segment)
    timeline_end = max(timeline_start, int(segment.get("end_ms", timeline_start + segment_duration)))
    timeline_duration = max(1, timeline_end)
    return round(available_offset * min(1.0, timeline_start / timeline_duration))


def _source_window(segment: dict, asset: Any, window_scorer: WindowScorer | None = None) -> tuple[int, int, float | None]:
    candidates = _window_candidates(segment, asset)
    if window_scorer is None or len(candidates) == 1:
        segment_duration = _duration(segment)
        start_ms = _timeline_source_start_ms(segment, max(0, _asset_duration_ms(asset) - segment_duration))
        end_ms = start_ms + segment_duration
        return start_ms, end_ms, None

    scored = [(float(window_scorer(asset, start_ms, end_ms)), start_ms, end_ms) for start_ms, end_ms in candidates]
    score, start_ms, end_ms = max(scored, key=lambda item: (item[0], item[1]))
    return start_ms, end_ms, score


def _scaled_bounds(segments: list[dict], target_duration_ms: int) -> list[tuple[int, int]]:
    if target_duration_ms <= 0:
        raise ValueError("target_duration_ms must be positive")
    source_duration = int(segments[-1]["end_ms"]) - int(segments[0]["start_ms"])
    if source_duration <= 0:
        raise ValueError("recipe duration must be positive")

    bounds: list[tuple[int, int]] = []
    cursor = 0
    elapsed_source = 0
    for index, segment in enumerate(segments):
        segment_duration = _duration(segment)
        if segment_duration <= 0:
            raise ValueError("recipe segments must have positive duration")
        elapsed_source += segment_duration
        if index == len(segments) - 1:
            end = target_duration_ms
        else:
            end = round(target_duration_ms * elapsed_source / source_duration)
        bounds.append((cursor, end))
        cursor = end
    if any(end <= start for start, end in bounds):
        raise ValueError("target_duration_ms is too short for the segment count")
    return bounds


def _source_path(asset: Any) -> str:
    path = _asset_field(asset, "path")
    if isinstance(path, Path):
        return path.as_posix()
    return str(path).replace("\\", "/")


def _role_score(role: str, asset: Any) -> tuple[float, list[str]]:
    if primary_role_for_asset({"path": _source_path(asset)}) == role:
        return 0.92, [f"filename-role:{role}"]
    return 0.55, ["fallback:first-available"]


def _candidate_for(segment: dict, asset: Any, window_scorer: WindowScorer | None = None) -> dict:
    confidence, evidence = _role_score(str(segment["role"]), asset)
    source_start_ms, source_end_ms, window_score = _source_window(segment, asset, window_scorer)
    if source_start_ms > 0:
        evidence = [*evidence, f"source-window:{source_start_ms}-{source_end_ms}"]
    if window_score is not None:
        evidence = [*evidence, f"window-score:{window_score:.3f}"]
    return {
        "asset_id": str(_asset_field(asset, "asset_id")),
        "source_path": _source_path(asset),
        "source_start_ms": source_start_ms,
        "source_end_ms": source_end_ms,
        "asset_duration_ms": _asset_duration_ms(asset),
        "score": confidence,
        "evidence": evidence,
        **({"window_score": window_score} if window_score is not None else {}),
    }


def _eligible_assets(segment: dict, assets: Iterable[Any]) -> list[Any]:
    needed = _duration(segment)
    return [asset for asset in assets if _asset_duration_ms(asset) >= needed]


def _pick_asset(segment: dict, assets: list[Any], recent_asset_ids: list[str]) -> Any | None:
    eligible = _eligible_assets(segment, assets)
    if not eligible:
        return None

    role_matches = [
        asset
        for asset in eligible
        if primary_role_for_asset({"path": _source_path(asset)}) == str(segment["role"])
    ]
    candidates = role_matches or eligible

    for asset in candidates:
        asset_id = str(_asset_field(asset, "asset_id"))
        if len(recent_asset_ids) < 2 or recent_asset_ids[-2:] != [asset_id, asset_id]:
            return asset
    return candidates[0]


def match_segments(
    segments: list[dict],
    assets: list[Any],
    threshold: float = 0.6,
    *,
    window_scorer: WindowScorer | None = None,
) -> dict:
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

        candidate = _candidate_for(segment, asset, window_scorer)
        confidence = float(candidate["score"])
        scores = {"filename": confidence}
        if "window_score" in candidate:
            scores["window"] = float(candidate["window_score"])
        output_candidate = {key: value for key, value in candidate.items() if key != "window_score"}
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
                "asset_duration_ms": int(candidate["asset_duration_ms"]),
                "confidence": confidence,
                "scores": scores,
                "candidates": [output_candidate],
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
    voiceover_path: Path | None = None,
    caption_burn_in: bool = False,
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
    if voiceover_path is not None:
        recipe["voiceover_path"] = voiceover_path.as_posix()
    if caption_burn_in:
        recipe["caption_burn_in"] = True

    validate_recipe(recipe)
    return recipe


def retime_recipe_and_matches(recipe: dict, matches: dict, target_duration_ms: int) -> tuple[dict, dict]:
    segments = recipe.get("segments", [])
    if not segments:
        raise ValueError("recipe has no segments")
    bounds = _scaled_bounds(segments, int(target_duration_ms))
    retimed_recipe = {
        **recipe,
        "duration_ms": int(target_duration_ms),
        "segments": [
            {**segment, "start_ms": start_ms, "end_ms": end_ms}
            for segment, (start_ms, end_ms) in zip(segments, bounds)
        ],
    }

    duration_by_segment_id = {
        str(segment["id"]): int(segment["end_ms"]) - int(segment["start_ms"])
        for segment in retimed_recipe["segments"]
    }
    retimed_matches = {
        **matches,
        "matches": [
            (
                _retime_match_source_window(match, duration_by_segment_id[str(match["segment_id"])])
                if match.get("status") in {"selected", "low_confidence"}
                else dict(match)
            )
            for match in matches.get("matches", [])
        ],
    }

    validate_recipe(retimed_recipe)
    validate_matches(retimed_matches)
    return retimed_recipe, retimed_matches


def _retime_match_source_window(match: dict, duration_ms: int) -> dict:
    asset_duration_ms = int(match.get("asset_duration_ms", match["source_end_ms"]))
    source_start_ms = int(match["source_start_ms"])
    source_start_ms = min(source_start_ms, max(0, asset_duration_ms - duration_ms))
    return {
        **match,
        "source_start_ms": source_start_ms,
        "source_end_ms": source_start_ms + duration_ms,
        "asset_duration_ms": asset_duration_ms,
    }
