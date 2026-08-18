from __future__ import annotations

import re

from jianji_flow.reference import ReferenceBeat


_PRODUCT_ROLES = ("hook", "pain", "feature", "evidence", "cta")
_PRODUCT_WEIGHTS = (15, 20, 25, 25, 15)
_TALKING_ROLES = ("topic", "claim", "explanation", "evidence", "conclusion")
_TALKING_WEIGHTS = (15, 20, 35, 20, 10)


def _roles_and_weights(mode: str) -> tuple[tuple[str, ...], tuple[int, ...]]:
    if mode == "product":
        return _PRODUCT_ROLES, _PRODUCT_WEIGHTS
    if mode == "talking-head":
        return _TALKING_ROLES, _TALKING_WEIGHTS
    raise ValueError(f"unsupported mode: {mode}")


def _split_script(script_text: str | None) -> list[str]:
    if not script_text:
        return []
    cleaned_lines = []
    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        if re.fullmatch(r"[\[\(（【]\s*\d{1,2}[^]\)）】]*[\]\)）】]", line):
            continue
        cleaned_lines.append(line)
    return [
        part.strip()
        for part in re.split(r"[\r\n.!?]+", "\n".join(cleaned_lines))
        if part.strip()
    ]


def _weighted_bounds(total_ms: int, weights: tuple[int, ...]) -> list[tuple[int, int]]:
    if total_ms < len(weights):
        raise ValueError("total_ms is too short for the segment count")

    starts: list[int] = []
    ends: list[int] = []
    elapsed = 0
    weight_total = sum(weights)
    for index, weight in enumerate(weights):
        starts.append(elapsed)
        if index == len(weights) - 1:
            elapsed = total_ms
        else:
            elapsed = round(total_ms * sum(weights[: index + 1]) / weight_total)
        ends.append(elapsed)

    if any(end <= start for start, end in zip(starts, ends)):
        raise ValueError("total_ms is too short for non-empty segments")
    return list(zip(starts, ends))


def default_beats(mode: str, total_ms: int) -> list[ReferenceBeat]:
    roles, weights = _roles_and_weights(mode)
    bounds = _weighted_bounds(total_ms, weights)
    return [
        ReferenceBeat(role=role, start_ms=start, end_ms=end, caption=role)
        for role, (start, end) in zip(roles, bounds)
    ]


def build_segment_plan(mode: str, total_ms: int, script_text: str | None) -> list[dict]:
    captions = _split_script(script_text)
    segments = []
    for index, beat in enumerate(default_beats(mode, total_ms), start=1):
        caption = captions[index - 1] if index <= len(captions) else beat.caption
        segments.append(
            {
                "id": f"seg-{index:03d}",
                "role": beat.role,
                "start_ms": beat.start_ms,
                "end_ms": beat.end_ms,
                "caption": caption,
            }
        )
    return segments
