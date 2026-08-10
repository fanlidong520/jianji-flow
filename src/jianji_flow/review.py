from __future__ import annotations

from pathlib import Path


def _match_by_id(matches: dict) -> dict[str, dict]:
    return {match["id"]: match for match in matches.get("matches", [])}


def _path_text(path: Path) -> str:
    return path.as_posix()


def build_review(recipe: dict, matches: dict, remix_path: Path, captions_path: Path) -> dict:
    by_id = _match_by_id(matches)
    failures: list[str] = []
    warnings: list[str] = []
    missing_segments: list[str] = []
    low_confidence_segments: list[str] = []

    for segment in recipe.get("segments", []):
        segment_id = segment.get("id", "unknown")
        match = by_id.get(segment.get("match_id"))
        if match is None:
            failures.append(f"{segment_id} missing match")
            missing_segments.append(str(segment_id))
            continue

        status = match.get("status")
        if status == "missing":
            reason = match.get("missing_reason", "no reason")
            failures.append(f"{segment_id} missing asset: {reason}")
            missing_segments.append(str(segment_id))
        elif status == "rejected":
            reason = match.get("rejected_reason", "no reason")
            failures.append(f"{segment_id} rejected: {reason}")
        elif status == "low_confidence":
            confidence = match.get("confidence", 0)
            warnings.append(f"{segment_id} low confidence: {confidence}")
            low_confidence_segments.append(str(segment_id))

    status = "fail" if failures else "warning" if warnings else "pass"
    return {
        "status": status,
        "failures": failures,
        "warnings": warnings,
        "missing_segments": missing_segments,
        "low_confidence_segments": low_confidence_segments,
        "outputs": {
            "remix": _path_text(remix_path),
            "captions": _path_text(captions_path),
        },
    }


def _list_section(title: str, values: list[str]) -> list[str]:
    lines = [f"## {title}"]
    if not values:
        lines.append("- none")
    else:
        lines.extend(f"- {value}" for value in values)
    return lines


def build_review_markdown(review: dict) -> str:
    lines = [
        "# jianji-flow Review",
        "",
        f"Status: {review.get('status', 'unknown')}",
        "",
        "## Outputs",
    ]
    outputs = review.get("outputs", {})
    if outputs:
        lines.extend(f"- {name}: {value}" for name, value in outputs.items())
    else:
        lines.append("- none")
    lines.append("")
    lines.extend(_list_section("Failures", list(review.get("failures", []))))
    lines.append("")
    lines.extend(_list_section("Warnings", list(review.get("warnings", []))))
    lines.append("")
    lines.extend(_list_section("Missing segments", list(review.get("missing_segments", []))))
    lines.append("")
    lines.extend(_list_section("Low confidence segments", list(review.get("low_confidence_segments", []))))
    lines.extend(
        [
            "",
            "## Manual review checklist",
            "- Check whether the opening enters the topic quickly.",
            "- Check whether each selected asset matches the segment caption.",
            "- Check for black frames, frozen frames, severe jumps, or distortion.",
            "- Check whether captions are readable and roughly synchronized.",
            "- Check whether warnings describe uncertainty honestly.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_review_markdown(review: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_review_markdown(review), encoding="utf-8")
