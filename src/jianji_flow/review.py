from __future__ import annotations

from html import escape
from pathlib import Path


def _match_by_id(matches: dict) -> dict[str, dict]:
    return {match["id"]: match for match in matches.get("matches", [])}


def _path_text(path: Path) -> str:
    return path.as_posix()


def build_review(
    recipe: dict,
    matches: dict,
    remix_path: Path,
    captions_path: Path,
    *,
    voiceover_path: Path | None = None,
    contact_sheet_path: Path | None = None,
    review_html_path: Path | None = None,
) -> dict:
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
    review = {
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
    return _with_optional_outputs(
        review,
        voiceover=voiceover_path,
        contact_sheet=contact_sheet_path,
        review_html=review_html_path,
    )


def _with_optional_outputs(review: dict, **paths: Path | None) -> dict:
    outputs = review.setdefault("outputs", {})
    for name, path in paths.items():
        if path is not None:
            outputs[name] = _path_text(path)
    return review


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


def build_review_html(review: dict, recipe: dict, matches: dict) -> str:
    outputs = review.get("outputs", {})
    match_by_id = _match_by_id(matches)
    rows = []
    for segment in recipe.get("segments", []):
        match = match_by_id.get(segment.get("match_id"), {})
        evidence = ", ".join(str(item) for item in match.get("evidence", []))
        rows.append(
            "<tr>"
            f"<td>{escape(str(segment.get('id', '')))}</td>"
            f"<td>{escape(str(segment.get('start_ms', '')))}-{escape(str(segment.get('end_ms', '')))}</td>"
            f"<td>{escape(str(segment.get('caption', '')))}</td>"
            f"<td>{escape(str(match.get('source_path', '')))}</td>"
            f"<td>{escape(str(match.get('confidence', '')))}</td>"
            f"<td>{escape(evidence)}</td>"
            "</tr>"
        )

    warnings = "".join(f"<li>{escape(str(item))}</li>" for item in review.get("warnings", [])) or "<li>none</li>"
    failures = "".join(f"<li>{escape(str(item))}</li>" for item in review.get("failures", [])) or "<li>none</li>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>jianji-flow review</title>
  <style>
    body {{ font-family: Arial, "Microsoft YaHei", sans-serif; margin: 24px; color: #151719; background: #f7f8fa; }}
    main {{ max-width: 1120px; margin: 0 auto; }}
    video, img {{ max-width: 100%; border: 1px solid #d6dae0; background: #000; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; background: #fff; }}
    th, td {{ border: 1px solid #d6dae0; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eef1f4; }}
    code {{ background: #eef1f4; padding: 2px 4px; }}
  </style>
</head>
<body>
<main>
  <h1>jianji-flow Review: {escape(str(review.get('status', 'unknown')))}</h1>
  <h2>Video</h2>
  <video controls src="{escape(str(outputs.get('remix', '')))}"></video>
  <h2>Contact Sheet</h2>
  <img alt="contact sheet" src="{escape(str(outputs.get('contact_sheet', '')))}">
  <h2>Outputs</h2>
  <ul>
    <li>Voiceover: <code>{escape(str(outputs.get('voiceover', '')))}</code></li>
    <li>Captions: <code>{escape(str(outputs.get('captions', '')))}</code></li>
    <li>Review HTML: <code>{escape(str(outputs.get('review_html', '')))}</code></li>
  </ul>
  <h2>Warnings</h2>
  <ul>{warnings}</ul>
  <h2>Failures</h2>
  <ul>{failures}</ul>
  <h2>Segments</h2>
  <table>
    <thead>
      <tr><th>Segment</th><th>Time</th><th>Caption</th><th>Asset</th><th>Confidence</th><th>Evidence</th></tr>
    </thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <h2>Manual Review Checklist</h2>
  <ul>
    <li>Opening enters the topic quickly.</li>
    <li>Each selected asset matches the segment caption.</li>
    <li>No black frames, frozen frames, severe jumps, or distortion.</li>
    <li>Captions are readable and roughly synchronized.</li>
    <li>Warnings describe uncertainty honestly.</li>
  </ul>
</main>
</body>
</html>
"""


def write_review_html(review: dict, recipe: dict, matches: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_review_html(review, recipe, matches), encoding="utf-8")
