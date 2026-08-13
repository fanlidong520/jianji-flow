from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from jianji_flow.asset_diagnosis import primary_role_for_asset

VisualSimilarityChecker = Callable[[str, str, int, int, int], bool]


def build_fixes_template(
    recipe: dict,
    matches: dict,
    assets: list[Any],
    review: dict,
    *,
    minimum_duration_recipe: dict | None = None,
    visual_similarity_checker: VisualSimilarityChecker | None = None,
) -> dict:
    match_by_id = {str(match.get("id")): match for match in matches.get("matches", [])}
    weak_roles = {str(role).casefold() for role in review.get("story_support", {}).get("weak_evidence_roles", [])}
    duration_by_segment_id = _duration_by_segment_id(minimum_duration_recipe or recipe)
    adjacent_sources_by_segment_id = _adjacent_sources_by_segment_id(recipe, match_by_id)
    used_recommendation_keys: set[str] = set()
    segments: dict[str, dict] = {}

    for segment in recipe.get("segments", []):
        segment_id = str(segment.get("id", ""))
        role = str(segment.get("role", "")).strip()
        match = match_by_id.get(str(segment.get("match_id")))
        reason = _fix_reason(role, match, weak_roles)
        if reason is None:
            continue

        current_path = _current_source_path(match)
        current_start_ms = _current_source_start_ms(match)
        candidate_assets = _candidate_assets(
            role,
            assets,
            exclude_path=current_path,
            minimum_duration_ms=duration_by_segment_id.get(segment_id, _segment_duration_ms(segment)),
            visual_duration_ms=_current_source_duration_ms(match) or _segment_duration_ms(segment),
            adjacent_sources=adjacent_sources_by_segment_id.get(segment_id, set()),
            visual_source_path=current_path,
            visual_source_start_ms=current_start_ms,
            visual_similarity_checker=visual_similarity_checker,
        )
        recommended = _recommended_candidate(candidate_assets, used_recommendation_keys)
        if recommended:
            recommendation_key = _path_key(recommended["asset_path"])
            if recommendation_key in used_recommendation_keys:
                _append_warning(recommended, "already recommended for another segment")
            else:
                used_recommendation_keys.add(recommendation_key)
        segments[segment_id] = {
            "role": role,
            "caption": str(segment.get("caption", "")),
            "reason": reason,
            "current_asset_path": current_path,
            "asset_path": "",
            "source_start_ms": None,
            "recommended_asset_path": recommended["asset_path"] if recommended else "",
            "recommendation_status": _recommendation_status(recommended),
            "recommendation_warnings": _recommendation_warnings(recommended, candidate_assets),
            "candidate_asset_paths": [candidate["asset_path"] for candidate in candidate_assets],
            "candidate_assets": candidate_assets,
        }

    return {
        "version": "0.1",
        "how_to_use": "Fill asset_path for any segment you want to replace, then rerun with --fixes fixes.template.json.",
        "segments": segments,
    }


def build_recommended_fixes(fixes: dict, target: str) -> dict:
    target_key = str(target).strip()
    segments = fixes.get("segments", {})
    if not target_key:
        raise ValueError("apply recommendation target is required")
    if not isinstance(segments, dict) or target_key not in segments:
        raise ValueError(f"recommendation target not found: {target_key}")

    segment = segments[target_key]
    if not isinstance(segment, dict):
        raise ValueError(f"recommendation target is invalid: {target_key}")
    status = str(segment.get("recommendation_status", ""))
    recommended_path = str(segment.get("recommended_asset_path", "")).strip()
    warnings = [str(item) for item in segment.get("recommendation_warnings", [])]
    if status != "recommended" or not recommended_path:
        warning_text = f": {'; '.join(warnings)}" if warnings else ""
        raise ValueError(f"recommendation for {target_key} is not clean: {status or 'unknown'}{warning_text}")
    return {
        "version": "0.1",
        "segments": {
            target_key: {
                "asset_path": recommended_path,
            }
        },
    }


def _duration_by_segment_id(recipe: dict) -> dict[str, int]:
    return {
        str(segment.get("id", "")): _segment_duration_ms(segment)
        for segment in recipe.get("segments", [])
    }


def _recommendation_status(candidate: dict | None) -> str:
    if candidate is None:
        return "no_candidate"
    if candidate.get("warnings"):
        return "best_available_with_warnings"
    return "recommended"


def _recommended_candidate(candidates: list[dict], used_recommendation_keys: set[str]) -> dict | None:
    role_matches = [candidate for candidate in candidates if candidate.get("role_match")]
    if not role_matches:
        return None
    unused = next(
        (candidate for candidate in role_matches if _path_key(str(candidate["asset_path"])) not in used_recommendation_keys),
        None,
    )
    return unused or role_matches[0]


def _recommendation_warnings(candidate: dict | None, candidates: list[dict]) -> list[str]:
    if candidate is not None:
        return list(candidate.get("warnings", []))
    if candidates:
        return ["no role-matching candidate"]
    return []


def _append_warning(candidate: dict, warning: str) -> None:
    warnings = list(candidate.get("warnings", []))
    if warning not in warnings:
        warnings.append(warning)
    candidate["warnings"] = warnings


def _adjacent_sources_by_segment_id(recipe: dict, match_by_id: dict[str, dict]) -> dict[str, set[str]]:
    segments = list(recipe.get("segments", []))
    result: dict[str, set[str]] = {}
    for index, segment in enumerate(segments):
        segment_id = str(segment.get("id", ""))
        adjacent_sources: set[str] = set()
        for adjacent_index in (index - 1, index + 1):
            if adjacent_index < 0 or adjacent_index >= len(segments):
                continue
            adjacent_match = match_by_id.get(str(segments[adjacent_index].get("match_id")))
            source_path = _current_source_path(adjacent_match)
            if source_path:
                adjacent_sources.add(_path_key(source_path))
        result[segment_id] = adjacent_sources
    return result


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


def _current_source_start_ms(match: dict | None) -> int:
    if not match:
        return 0
    try:
        return max(0, int(match.get("source_start_ms", 0)))
    except (TypeError, ValueError):
        return 0


def _current_source_duration_ms(match: dict | None) -> int:
    if not match:
        return 0
    try:
        start_ms = int(match.get("source_start_ms", 0))
        end_ms = int(match.get("source_end_ms", 0))
    except (TypeError, ValueError):
        return 0
    return max(0, end_ms - start_ms)


def _segment_duration_ms(segment: dict) -> int:
    try:
        return max(0, int(segment.get("end_ms", 0)) - int(segment.get("start_ms", 0)))
    except (TypeError, ValueError):
        return 0


def _candidate_assets(
    role: str,
    assets: list[Any],
    *,
    exclude_path: str,
    minimum_duration_ms: int,
    visual_duration_ms: int,
    adjacent_sources: set[str],
    visual_source_path: str,
    visual_source_start_ms: int,
    visual_similarity_checker: VisualSimilarityChecker | None,
) -> list[dict]:
    exclude = _path_key(exclude_path)
    candidates = [
        (
            index,
            _candidate_asset(
                role,
                asset,
                adjacent_sources,
                visual_source_path=visual_source_path,
                visual_source_start_ms=visual_source_start_ms,
                visual_duration_ms=visual_duration_ms,
                minimum_duration_ms=minimum_duration_ms,
                visual_similarity_checker=visual_similarity_checker,
            ),
        )
        for index, asset in enumerate(assets)
        if _asset_duration_ms(asset) >= minimum_duration_ms and _path_key(_asset_path(asset)) != exclude
    ]
    return [
        candidate
        for _, candidate in sorted(candidates, key=lambda item: (-item[1]["score"], item[0]))
    ]


def _candidate_asset(
    role: str,
    asset: Any,
    adjacent_sources: set[str],
    *,
    visual_source_path: str,
    visual_source_start_ms: int,
    visual_duration_ms: int,
    minimum_duration_ms: int,
    visual_similarity_checker: VisualSimilarityChecker | None,
) -> dict:
    asset_path = _asset_path(asset)
    asset_role = primary_role_for_asset({"path": asset_path})
    repeats_adjacent = _path_key(asset_path) in adjacent_sources
    reasons = []
    warnings = []
    score = 0
    if asset_role == role:
        reasons.append(f"matches role {role}")
        score += 20
    else:
        reasons.append("fallback candidate")
        warnings.append("role mismatch; filename-only fallback")
    if repeats_adjacent:
        warnings.append("would repeat adjacent segment")
        score -= 10
    else:
        reasons.append("avoids adjacent repetition")
        score += 50
    if visual_similarity_checker is not None and visual_source_path and asset_role == role:
        visual_candidate_start_ms = min(visual_source_start_ms, max(0, _asset_duration_ms(asset) - visual_duration_ms))
        try:
            visually_similar = visual_similarity_checker(
                visual_source_path,
                asset_path,
                visual_duration_ms,
                visual_source_start_ms,
                visual_candidate_start_ms,
            )
        except (OSError, RuntimeError, ValueError):
            warnings.append("visual similarity check failed")
            score -= 40
        else:
            if not visually_similar:
                reasons.append("visually distinct from current segment")
                score += 10
            else:
                warnings.append("visually similar to current segment")
                score -= 60
    return {
        "asset_path": asset_path,
        "score": score,
        "reasons": reasons,
        "warnings": warnings,
        "role_match": asset_role == role,
    }


def _asset_path(asset: Any) -> str:
    path = asset["path"] if isinstance(asset, dict) else getattr(asset, "path")
    if isinstance(path, Path):
        return path.as_posix()
    return str(path).replace("\\", "/")


def _asset_duration_ms(asset: Any) -> int:
    return int(asset["duration_ms"] if isinstance(asset, dict) else getattr(asset, "duration_ms"))


def _path_key(path_text: str) -> str:
    return path_text.replace("\\", "/").casefold()
