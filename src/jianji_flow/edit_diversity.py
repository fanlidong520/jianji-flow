from __future__ import annotations

from collections import Counter
from pathlib import Path


def diagnose_edit_diversity(recipe: dict, matches: dict) -> dict:
    match_by_id = {str(match.get("id")): match for match in matches.get("matches", [])}
    selected: list[dict] = []
    for segment in recipe.get("segments", []):
        match = match_by_id.get(str(segment.get("match_id")))
        if match and match.get("status") in {"selected", "low_confidence"}:
            selected.append(match)

    sources = [_source_key(match) for match in selected if _source_key(match)]
    windows = [_window_key(match) for match in selected if _window_key(match)]
    warning = _reuse_warning(sources)
    return {
        "status": "warning" if warning else "pass" if selected else "not_applicable",
        "selected_segment_count": len(selected),
        "distinct_source_video_count": len(set(sources)),
        "distinct_source_window_count": len(set(windows)),
        "most_reused_source": _most_common_source(sources),
        "most_reused_source_count": _most_common_source_count(sources),
        "warnings": [warning] if warning else [],
    }


def _source_key(match: dict) -> str:
    source_path = match.get("source_path")
    if not isinstance(source_path, str) or not source_path.strip():
        return ""
    return Path(source_path).as_posix().casefold()


def _window_key(match: dict) -> str:
    source = _source_key(match)
    if not source:
        return ""
    return f"{source}#{match.get('source_start_ms', '')}-{match.get('source_end_ms', '')}"


def _reuse_warning(sources: list[str]) -> str:
    if len(sources) < 3:
        return ""
    source, count = Counter(sources).most_common(1)[0]
    threshold = max(3, round(len(sources) * 0.67))
    if count < threshold:
        return ""
    source_name = Path(source).name or source
    return (
        f"Edit diversity is weak: {count} of {len(sources)} segments come from the same source video "
        f"({source_name}); the result may look like a voiceover shell instead of a true remix. "
        "Compare it with the original before using."
    )


def _most_common_source(sources: list[str]) -> str:
    if not sources:
        return ""
    return Counter(sources).most_common(1)[0][0]


def _most_common_source_count(sources: list[str]) -> int:
    if not sources:
        return 0
    return int(Counter(sources).most_common(1)[0][1])
