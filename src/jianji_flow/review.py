from __future__ import annotations

from copy import deepcopy
from html import escape
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from PIL import ImageStat

from jianji_flow.media_probe import run_ffprobe
from jianji_flow.quality_diagnosis import diagnose_contact_sheet_segments
from jianji_flow.review_summary import build_review_summary
from jianji_flow.voiceover import validate_voiceover


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
    ass_path: Path | None = None,
    voiceover_path: Path | None = None,
    contact_sheet_path: Path | None = None,
    review_html_path: Path | None = None,
    check_artifacts: bool = True,
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

    if check_artifacts:
        artifact_result = _artifact_review(recipe, remix_path, captions_path, ass_path, voiceover_path, contact_sheet_path)
        failures.extend(artifact_result["failures"])
        warnings.extend(artifact_result["warnings"])

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
    review["summary"] = build_review_summary(review)
    return _with_optional_outputs(
        review,
        captions_ass=ass_path,
        voiceover=voiceover_path,
        contact_sheet=contact_sheet_path,
        review_html=review_html_path,
    )


def _duration_tolerance_ms(duration_ms: int) -> int:
    return max(200, round(duration_ms * 0.02))


def _artifact_review(
    recipe: dict,
    remix_path: Path,
    captions_path: Path,
    ass_path: Path | None,
    voiceover_path: Path | None,
    contact_sheet_path: Path | None,
) -> dict:
    failures = []
    warnings = []
    expected_duration = int(recipe.get("duration_ms", 0) or 0)
    if not remix_path.exists():
        failures.append(f"remix missing: {remix_path}")
    else:
        try:
            info = run_ffprobe(remix_path)
            if not info.has_audio:
                failures.append("remix has no audio stream")
            if expected_duration > 0 and abs(info.duration_ms - expected_duration) > _duration_tolerance_ms(expected_duration):
                failures.append(f"remix duration {info.duration_ms}ms does not match recipe {expected_duration}ms")
        except (RuntimeError, ValueError) as exc:
            failures.append(f"remix probe failed: {exc}")

    if not captions_path.exists() or captions_path.stat().st_size <= 0:
        failures.append(f"captions missing or empty: {captions_path}")

    if recipe.get("caption_burn_in"):
        if ass_path is None:
            failures.append("captions.ass path is required when caption_burn_in is true")
        elif not ass_path.exists() or ass_path.stat().st_size <= 0:
            failures.append(f"captions.ass missing or empty: {ass_path}")

    if voiceover_path is not None:
        try:
            validate_voiceover(voiceover_path, expected_duration_ms=expected_duration)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            failures.append(f"voiceover invalid: {exc}")

    expected_segments = len(recipe.get("segments", []))
    if contact_sheet_path is None:
        failures.append("contact sheet path is required")
    elif not contact_sheet_path.exists() or contact_sheet_path.stat().st_size <= 0:
        failures.append(f"contact sheet missing or empty: {contact_sheet_path}")
    else:
        try:
            with Image.open(contact_sheet_path) as image:
                image.verify()
            with Image.open(contact_sheet_path) as image:
                if image.width <= 0 or image.height <= 0:
                    failures.append(f"contact sheet has invalid dimensions: {contact_sheet_path}")
                elif expected_segments > 0 and image.width < expected_segments * 100:
                    failures.append(
                        f"contact sheet is too narrow for {expected_segments} segments: {image.width}px"
                    )
                elif not _has_contact_sheet_visual_detail(image):
                    failures.append(f"contact sheet has insufficient visual detail: {contact_sheet_path}")
                else:
                    diagnosis = diagnose_contact_sheet_segments(contact_sheet_path, recipe)
                    warnings.extend(diagnosis.get("warnings", []))
        except (OSError, UnidentifiedImageError) as exc:
            failures.append(f"contact sheet is not a readable image: {exc}")

    return {"failures": failures, "warnings": warnings}


def _has_contact_sheet_visual_detail(image: Image.Image) -> bool:
    rgb = image.convert("RGB")
    full_stat = ImageStat.Stat(rgb)
    lower_band = rgb.crop((0, round(rgb.height * 0.7), rgb.width, rgb.height))
    lower_stat = ImageStat.Stat(lower_band)
    return max(full_stat.stddev) > 8 and max(lower_stat.stddev) > 8


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
    summary = review.get("summary", build_review_summary(review))
    lines = [
        "# jianji-flow Review",
        "",
        f"Status: {review.get('status', 'unknown')}",
        "",
        "## Summary",
        f"- Decision: {summary.get('decision', 'Unknown')}",
        f"- Reason: {summary.get('reason', '')}",
        f"- Next action: {summary.get('next_action', '')}",
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
    summary = review.get("summary", build_review_summary(review))
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
  <section>
    <h2>Summary</h2>
    <p><strong>Decision:</strong> {escape(str(summary.get('decision', 'Unknown')))}</p>
    <p><strong>Reason:</strong> {escape(str(summary.get('reason', '')))}</p>
    <p><strong>Next action:</strong> {escape(str(summary.get('next_action', '')))}</p>
  </section>
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
    output_path.write_text(
        build_review_html(_html_review_paths(review, output_path.parent), recipe, matches),
        encoding="utf-8",
    )


def _html_review_paths(review: dict, base_dir: Path) -> dict:
    html_review = deepcopy(review)
    outputs = html_review.get("outputs", {})
    for key, value in list(outputs.items()):
        if not isinstance(value, str) or not value:
            continue
        try:
            candidate = Path(value)
            if candidate.is_absolute():
                outputs[key] = candidate.resolve().relative_to(base_dir.resolve()).as_posix()
        except (OSError, ValueError):
            continue
    return html_review
