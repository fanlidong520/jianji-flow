from __future__ import annotations

from copy import deepcopy
from collections import Counter
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
    shot_contact_sheet_path: Path | None = None,
    reference_comparison_path: Path | None = None,
    shot_plan: dict | None = None,
    review_html_path: Path | None = None,
    check_artifacts: bool = True,
    visual_selection: dict | None = None,
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

    warnings.extend(_source_diversity_warnings(recipe, matches))
    warnings.extend(_adjacent_source_warnings(recipe, matches))
    warnings.extend(_match_evidence_warnings(recipe, matches))
    story_support = _story_support(recipe, matches)
    if story_support["status"] == "fail":
        failures.append(story_support["warning"])
    elif story_support["status"] == "weak":
        warnings.append(story_support["warning"])

    if shot_plan:
        warnings.extend(str(item) for item in shot_plan.get("warnings", []))

    if check_artifacts:
        artifact_result = _artifact_review(
            recipe,
            remix_path,
            captions_path,
            ass_path,
            voiceover_path,
            contact_sheet_path,
            shot_contact_sheet_path,
            reference_comparison_path,
        )
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
        "story_support": story_support,
    }
    if visual_selection:
        review["visual_selection"] = visual_selection
    if shot_plan:
        review["shot_plan"] = shot_plan
    review["summary"] = build_review_summary(review)
    return _with_optional_outputs(
        review,
        captions_ass=ass_path,
        voiceover=voiceover_path,
        contact_sheet=contact_sheet_path,
        shot_contact_sheet=shot_contact_sheet_path,
        reference_comparison=reference_comparison_path,
        review_html=review_html_path,
    )


def _source_diversity_warnings(recipe: dict, matches: dict) -> list[str]:
    by_id = _match_by_id(matches)
    sources: list[str] = []
    for segment in recipe.get("segments", []):
        match = by_id.get(segment.get("match_id"))
        if not match or match.get("status") not in {"selected", "low_confidence"}:
            continue
        source_path = match.get("source_path")
        if isinstance(source_path, str) and source_path.strip():
            sources.append(Path(source_path).as_posix().casefold())

    if len(sources) < 3:
        return []
    source, count = Counter(sources).most_common(1)[0]
    threshold = max(3, round(len(sources) * 0.67))
    if count < threshold:
        return []
    return [
        f"{count} of {len(sources)} segments come from the same source video; "
        "the result may look like a voiceover shell instead of a true remix. "
        "Compare it with the original before using."
    ]


def _adjacent_source_warnings(recipe: dict, matches: dict) -> list[str]:
    by_id = _match_by_id(matches)
    warnings: list[str] = []
    previous_segment_id = ""
    previous_source = ""
    for segment in recipe.get("segments", []):
        match = by_id.get(segment.get("match_id"))
        if not match or match.get("status") not in {"selected", "low_confidence"}:
            previous_segment_id = ""
            previous_source = ""
            continue
        source_path = match.get("source_path")
        source = Path(source_path).as_posix().casefold() if isinstance(source_path, str) and source_path else ""
        segment_id = str(segment.get("id", "unknown"))
        if source and previous_source and source == previous_source:
            warnings.append(
                f"Adjacent segments {previous_segment_id} and {segment_id} use the same source video; "
                "the cut may feel repetitive after fixes."
            )
        previous_segment_id = segment_id
        previous_source = source
    return warnings


def _match_evidence_warnings(recipe: dict, matches: dict) -> list[str]:
    by_id = _match_by_id(matches)
    selected = []
    filename_only = []
    for segment in recipe.get("segments", []):
        match = by_id.get(segment.get("match_id"))
        if not match or match.get("status") not in {"selected", "low_confidence"}:
            continue
        selected.append(match)
        evidence = [str(item) for item in match.get("evidence", [])]
        if evidence and any(item.startswith("filename-role:") for item in evidence) and not any(
            _is_visual_evidence(item) for item in evidence
        ):
            filename_only.append(str(segment.get("id", "unknown")))

    if len(selected) < 3:
        return []
    if len(filename_only) < max(3, round(len(selected) * 0.8)):
        return []
    return [
        f"{len(filename_only)} of {len(selected)} selected segments are filename only matches; "
        "jianji-flow assembled role-labeled clips but did not verify the visuals. "
        "Watch the contact sheet before treating this as a usable cut."
    ]


def _story_support(recipe: dict, matches: dict) -> dict:
    by_id = _match_by_id(matches)
    story_label = _story_label(recipe.get("mode"))
    roles: list[str] = []
    filename_only_roles: list[str] = []
    visual_evidence_roles: list[str] = []
    weak_evidence_roles: list[str] = []
    for segment in recipe.get("segments", []):
        match = by_id.get(segment.get("match_id"))
        if not match or match.get("status") not in {"selected", "low_confidence"}:
            continue
        role = str(segment.get("role") or segment.get("caption") or segment.get("id", "unknown")).strip().casefold()
        roles.append(role)
        evidence = [str(item) for item in match.get("evidence", [])]
        has_visual_evidence = any(_is_visual_evidence(item) for item in evidence)
        if evidence and any(item.startswith("filename-role:") for item in evidence) and not has_visual_evidence:
            filename_only_roles.append(role)
        if has_visual_evidence:
            visual_evidence_roles.append(role)
        else:
            weak_evidence_roles.append(role)

    if not roles:
        return {
            "status": "fail",
            "roles": [],
            "filename_only_roles": [],
            "visual_evidence_roles": [],
            "weak_evidence_roles": [],
            "next_action": "Add usable clips for the planned story roles, then rerun.",
            "warning": "No selected clips support the story.",
        }

    if weak_evidence_roles:
        return {
            "status": "weak",
            "roles": roles,
            "filename_only_roles": filename_only_roles,
            "visual_evidence_roles": visual_evidence_roles,
            "weak_evidence_roles": weak_evidence_roles,
            "next_action": _story_next_action(weak_evidence_roles),
            "warning": (
                f"Story support is weak: {len(weak_evidence_roles)} of {len(roles)} {story_label} roles do not have "
                f"visual evidence, so the {story_label} must be checked manually."
            ),
        }
    return {
        "status": "pass",
        "roles": roles,
        "filename_only_roles": filename_only_roles,
        "visual_evidence_roles": visual_evidence_roles,
        "weak_evidence_roles": weak_evidence_roles,
        "next_action": "Review the rough cut, captions, and product accuracy before publishing.",
    }


def _is_visual_evidence(item: str) -> bool:
    return item.startswith(("visual-frame:", "visual-review:"))


def _story_label(mode: object) -> str:
    if mode == "talking-head":
        return "talking-head story"
    return "product story"


def _story_next_action(weak_roles: list[str]) -> str:
    if not weak_roles:
        return "Review the rough cut before publishing."
    roles = ", ".join(weak_roles)
    noun = "clip" if len(weak_roles) == 1 else "clips"
    return f"Replace or manually verify {roles} {noun}; add clearer role-labeled material if the contact sheet does not support the script."


def _duration_tolerance_ms(duration_ms: int) -> int:
    return max(200, round(duration_ms * 0.02))


def _artifact_review(
    recipe: dict,
    remix_path: Path,
    captions_path: Path,
    ass_path: Path | None,
    voiceover_path: Path | None,
    contact_sheet_path: Path | None,
    shot_contact_sheet_path: Path | None,
    reference_comparison_path: Path | None,
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
                    failures.extend(diagnosis.get("failures", []))
                    warnings.extend(diagnosis.get("warnings", []))
        except (OSError, UnidentifiedImageError) as exc:
            failures.append(f"contact sheet is not a readable image: {exc}")

    if reference_comparison_path is not None:
        if not reference_comparison_path.exists() or reference_comparison_path.stat().st_size <= 0:
            failures.append(f"reference comparison sheet missing or empty: {reference_comparison_path}")
        else:
            try:
                with Image.open(reference_comparison_path) as image:
                    image.verify()
            except (OSError, UnidentifiedImageError) as exc:
                failures.append(f"reference comparison sheet invalid: {exc}")

    if shot_contact_sheet_path is not None:
        if not shot_contact_sheet_path.exists() or shot_contact_sheet_path.stat().st_size <= 0:
            failures.append(f"shot contact sheet missing or empty: {shot_contact_sheet_path}")
        else:
            try:
                with Image.open(shot_contact_sheet_path) as image:
                    image.verify()
            except (OSError, UnidentifiedImageError) as exc:
                failures.append(f"shot contact sheet invalid: {exc}")

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


def _story_support_section(story_support: dict | None) -> list[str]:
    lines = ["## Story support"]
    if not story_support:
        lines.append("- none")
        return lines
    lines.append(f"- status: {story_support.get('status', 'unknown')}")
    for key in ("roles", "filename_only_roles", "visual_evidence_roles", "weak_evidence_roles"):
        values = [str(item) for item in story_support.get(key, [])]
        lines.append(f"- {key}: {', '.join(values) if values else 'none'}")
    if story_support.get("next_action"):
        lines.append(f"- next_action: {story_support['next_action']}")
    return lines


def _story_support_html(story_support: dict | None) -> str:
    if not story_support:
        return "<li>none</li>"
    items = [f"<li>status: <code>{escape(str(story_support.get('status', 'unknown')))}</code></li>"]
    for key in ("roles", "filename_only_roles", "visual_evidence_roles", "weak_evidence_roles"):
        values = ", ".join(str(item) for item in story_support.get(key, [])) or "none"
        items.append(f"<li>{escape(key)}: <code>{escape(values)}</code></li>")
    if story_support.get("next_action"):
        items.append(f"<li>next_action: {escape(str(story_support['next_action']))}</li>")
    return "".join(items)


def _storyboard_rows(recipe: dict | None, matches: dict | None, review: dict) -> list[dict[str, str]]:
    if not recipe or not matches:
        return []
    match_by_id = _match_by_id(matches)
    warnings = [str(item) for item in review.get("warnings", [])]
    rows: list[dict[str, str]] = []
    for segment in recipe.get("segments", []):
        segment_id = str(segment.get("id", ""))
        match = match_by_id.get(segment.get("match_id"), {})
        evidence = [str(item) for item in match.get("evidence", [])]
        risks = _storyboard_risks(segment_id, match, evidence, warnings)
        source_start = match.get("source_start_ms", "")
        source_end = match.get("source_end_ms", "")
        source_range = (
            f"{source_start}-{source_end}ms"
            if isinstance(source_start, int) and isinstance(source_end, int)
            else ""
        )
        rows.append(
            {
                "segment_id": segment_id,
                "role": str(segment.get("role", "")),
                "time": f"{segment.get('start_ms', '')}-{segment.get('end_ms', '')}ms",
                "caption": str(segment.get("caption", "")),
                "asset": str(match.get("source_path", "")),
                "source_range": source_range,
                "confidence": str(match.get("confidence", "")),
                "evidence": ", ".join(evidence) if evidence else "none",
                "risk": "; ".join(risks) if risks else "none",
            }
        )
    return rows


def _storyboard_risks(segment_id: str, match: dict, evidence: list[str], warnings: list[str]) -> list[str]:
    risks: list[str] = []
    status = match.get("status")
    if status == "low_confidence":
        risks.append("low confidence")
    elif status == "missing":
        risks.append("missing asset")
    if evidence and any(item.startswith("filename-role:") for item in evidence) and not any(
        _is_visual_evidence(item) for item in evidence
    ):
        risks.append("filename-only match")
    risks.extend(warning for warning in warnings if segment_id and segment_id in warning)
    return risks


def _storyboard_markdown_section(recipe: dict | None, matches: dict | None, review: dict) -> list[str]:
    lines = ["## Storyboard"]
    rows = _storyboard_rows(recipe, matches, review)
    if not rows:
        lines.append("- none")
        return lines
    lines.append("| Segment | Role | Caption | Asset | Source range | Evidence | Risk |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(row[key])
                for key in ("segment_id", "role", "caption", "asset", "source_range", "evidence", "risk")
            )
            + " |"
        )
    return lines


def _visual_selection_markdown_section(visual_selection: dict | None) -> list[str]:
    lines = ["## Visual selection"]
    if not visual_selection:
        lines.append("- none")
        return lines
    lines.append("Codex visual review is model-assisted evidence; local quality metrics are not semantic proof.")
    if visual_selection.get("candidate_sheet"):
        lines.append(f"- candidate_sheet: {visual_selection['candidate_sheet']}")
    selections = [item for item in visual_selection.get("selections", []) if isinstance(item, dict)]
    if not selections:
        lines.append("- none")
        return lines
    lines.append("| Segment | Candidate | Reviewer | Reason | Frames |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in selections:
        frames = ", ".join(str(frame) for frame in item.get("frames", [])) or "none"
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(str(value))
                for value in (
                    item.get("segment_id", ""),
                    item.get("candidate_id", ""),
                    item.get("reviewer", ""),
                    item.get("reason", ""),
                    frames,
                )
            )
            + " |"
        )
    final_selections = [item for item in selections if item.get("final_frames")]
    if final_selections:
        lines.extend(
            [
                "",
                "Final selected frames are sampled from the final retimed source ranges:",
                "| Segment | Final source range | Final frames |",
                "| --- | --- | --- |",
            ]
        )
        for item in final_selections:
            lines.append(
                "| "
                + " | ".join(
                    _markdown_cell(str(value))
                    for value in (
                        item.get("segment_id", ""),
                        item.get("final_source_range", ""),
                        ", ".join(str(frame) for frame in item.get("final_frames", [])),
                    )
                )
                + " |"
            )
    return lines


def _shot_plan_markdown_section(shot_plan: dict | None) -> list[str]:
    if not shot_plan:
        return []
    lines = [
        "## Shot plan",
        "Scene boundaries are structural evidence only; they do not prove semantic visual matching.",
        f"- status: {shot_plan.get('status', 'unknown')}",
        f"- total shots: {shot_plan.get('total_shots', 0)}",
        "| Segment | Shot count | Status | Boundaries |",
        "| --- | ---: | --- | --- |",
    ]
    for item in shot_plan.get("segments", []):
        boundaries = ", ".join(f"{value}ms" for value in item.get("boundaries_ms", [])) or "none"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("segment_id", "")),
                    str(item.get("shot_count", "")),
                    str(item.get("status", "")),
                    boundaries,
                ]
            )
            + " |"
        )
    return lines


def _visual_selection_html(visual_selection: dict | None) -> str:
    if not visual_selection:
        return "<p>none</p>"
    intro = "<p>Codex visual review is model-assisted evidence; local quality metrics are not semantic proof.</p>"
    sheet = ""
    if visual_selection.get("candidate_sheet"):
        sheet = (
            f'<figure><img alt="visual candidate sheet" src="{escape(str(visual_selection["candidate_sheet"]))}">'
            "<figcaption>Candidate sheet</figcaption></figure>"
        )
    rows = []
    for item in visual_selection.get("selections", []):
        if not isinstance(item, dict):
            continue
        frame_html = "".join(
            f'<img alt="visual candidate frame" src="{escape(str(frame))}">'
            for frame in item.get("frames", [])
        ) or "none"
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('segment_id', '')))}</td>"
            f"<td>{escape(str(item.get('candidate_id', '')))}</td>"
            f"<td>{escape(str(item.get('reviewer', '')))}</td>"
            f"<td>{escape(str(item.get('reason', '')))}</td>"
            f"<td class=\"visual-selection-frames\">{frame_html}</td>"
            "</tr>"
        )
    table = (
        "<table><thead><tr><th>Segment</th><th>Candidate</th><th>Reviewer</th><th>Reason</th><th>Frames</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    final_rows = []
    for item in visual_selection.get("selections", []):
        if not isinstance(item, dict) or not item.get("final_frames"):
            continue
        frames = "".join(
            f'<img alt="final selected frame" src="{escape(str(frame))}">'
            for frame in item.get("final_frames", [])
        )
        final_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('segment_id', '')))}</td>"
            f"<td>{escape(str(item.get('final_source_range', '')))}</td>"
            f"<td class=\"visual-selection-frames\">{frames}</td>"
            "</tr>"
        )
    final_table = ""
    if final_rows:
        final_table = (
            "<h3>Final selected frames</h3>"
            "<p>These frames are sampled from the final retimed source ranges.</p>"
            "<table><thead><tr><th>Segment</th><th>Final source range</th><th>Frames</th></tr></thead>"
            f"<tbody>{''.join(final_rows)}</tbody></table>"
        )
    return intro + sheet + table + final_table


def _shot_plan_html(shot_plan: dict | None) -> str:
    if not shot_plan:
        return ""
    rows = []
    for item in shot_plan.get("segments", []):
        boundaries = ", ".join(f"{value}ms" for value in item.get("boundaries_ms", [])) or "none"
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('segment_id', '')))}</td>"
            f"<td>{escape(str(item.get('shot_count', '')))}</td>"
            f"<td>{escape(str(item.get('status', '')))}</td>"
            f"<td>{escape(boundaries)}</td>"
            "</tr>"
        )
    return (
        "<h2>Shot plan</h2>"
        "<p>Scene boundaries are structural evidence only; they do not prove semantic visual matching.</p>"
        f"<p><strong>Status:</strong> {escape(str(shot_plan.get('status', 'unknown')))} "
        f"<strong>Total shots:</strong> {escape(str(shot_plan.get('total_shots', 0)))}</p>"
        "<table><thead><tr><th>Segment</th><th>Shot count</th><th>Status</th><th>Boundaries</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _change_report_markdown_section(change_report: dict | None) -> list[str]:
    lines = ["## Change report"]
    if not change_report:
        lines.append("- none")
        return lines
    lines.append("Picture change only means sampled frames differ; it does not prove the new shot fits the script.")
    changed_segments = [item for item in change_report.get("changed_segments", []) if isinstance(item, dict)]
    if not changed_segments:
        lines.append("- No segments changed.")
    else:
        lines.append("| Segment | Role | Caption | Before | After | Picture change | Sampling note | Reason |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for item in changed_segments:
            lines.append(
                "| "
                + " | ".join(
                    _markdown_cell(value)
                    for value in (
                        str(item.get("segment_id", "")),
                        str(item.get("role", "")),
                        str(item.get("caption", "")),
                        _asset_range_text(item.get("before_asset"), item.get("before_range"), item.get("before_frame")),
                        _asset_range_text(item.get("after_asset"), item.get("after_range"), item.get("after_frame")),
                        _difference_text(item.get("visual_difference")),
                        str(item.get("visual_difference_warning", "")) or "ok",
                        str(item.get("reason", "")),
                    )
                )
                + " |"
            )
    unchanged_segments = [str(item) for item in change_report.get("unchanged_segments", [])]
    if unchanged_segments:
        lines.append(f"- Unchanged segments: {', '.join(unchanged_segments)}")
    unaccounted_segments = [str(item) for item in change_report.get("unaccounted_segments", [])]
    if unaccounted_segments:
        lines.append(f"- Unaccounted segments: {', '.join(unaccounted_segments)}")
    return lines


def _asset_range_text(asset: object, source_range: object, frame: object = "") -> str:
    asset_text = str(asset or "")
    range_text = str(source_range or "")
    frame_text = str(frame or "")
    if asset_text and range_text:
        text = f"{asset_text} @ {range_text}"
    else:
        text = asset_text or range_text or "unknown"
    if frame_text:
        return f"{text}; frame: {frame_text}"
    return text


def _difference_text(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value) if value not in (None, "") else "unknown"


def _markdown_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _storyboard_html(recipe: dict | None, matches: dict | None, review: dict) -> str:
    rows = _storyboard_rows(recipe, matches, review)
    if not rows:
        return "<p>none</p>"
    body = []
    for row in rows:
        risk_class = " risk-none" if row["risk"] == "none" else " risk-warning"
        body.append(
            f"<article class=\"storyboard-row{risk_class}\">"
            f"<div class=\"storyboard-head\"><span>{escape(row['segment_id'])}</span><strong>{escape(row['role'])}</strong></div>"
            f"<p class=\"storyboard-caption\">{escape(row['caption'])}</p>"
            f"<dl>"
            f"<dt>Asset</dt><dd>{escape(row['asset'])}</dd>"
            f"<dt>Source range</dt><dd>{escape(row['source_range'] or 'unknown')}</dd>"
            f"<dt>Evidence</dt><dd>{escape(row['evidence'])}</dd>"
            f"<dt>Risk</dt><dd>{escape(row['risk'])}</dd>"
            f"</dl>"
            "</article>"
        )
    return "".join(body)


def _change_report_html(change_report: dict | None) -> str:
    if not change_report:
        return "<p>none</p>"
    intro = "<p>Picture change only means sampled frames differ; it does not prove the new shot fits the script.</p>"
    changed_segments = [item for item in change_report.get("changed_segments", []) if isinstance(item, dict)]
    if not changed_segments:
        body = "<p>No segments changed.</p>"
    else:
        rows = []
        for item in changed_segments:
            rows.append(
                "<tr>"
                f"<td>{escape(str(item.get('segment_id', '')))}</td>"
                f"<td>{escape(str(item.get('role', '')))}</td>"
                f"<td>{escape(str(item.get('caption', '')))}</td>"
                f"<td>{_change_frame_html(item, 'before')}</td>"
                f"<td>{_change_frame_html(item, 'after')}</td>"
                f"<td>{escape(_difference_text(item.get('visual_difference')))}</td>"
                f"<td>{escape(str(item.get('visual_difference_warning', '')) or 'ok')}</td>"
                f"<td>{escape(str(item.get('reason', '')))}</td>"
                "</tr>"
            )
        body = (
            "<table>"
            "<thead><tr><th>Segment</th><th>Role</th><th>Caption</th><th>Before</th><th>After</th><th>Picture change</th><th>Sampling note</th><th>Reason</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
    unchanged_segments = [str(item) for item in change_report.get("unchanged_segments", [])]
    if unchanged_segments:
        body += f"<p>Unchanged segments: {escape(', '.join(unchanged_segments))}</p>"
    unaccounted_segments = [str(item) for item in change_report.get("unaccounted_segments", [])]
    if unaccounted_segments:
        body += f"<p>Unaccounted segments: {escape(', '.join(unaccounted_segments))}</p>"
    return intro + body


def _change_report_section_html(change_report: dict | None) -> str:
    if not change_report:
        return ""
    return f"<h2>Change report</h2><section>{_change_report_html(change_report)}</section>"


def _change_frame_html(item: dict, side: str) -> str:
    asset = item.get(f"{side}_asset")
    source_range = item.get(f"{side}_range")
    frame = str(item.get(f"{side}_frame", "") or "")
    text = escape(_asset_range_text(asset, source_range))
    if not frame:
        return text
    return f'<figure><img alt="{escape(side)} change frame" src="{escape(frame)}"><figcaption>{text}</figcaption></figure>'


def _outputs_html(outputs: dict) -> str:
    if not outputs:
        return "<li>none</li>"
    items = []
    for name, value in outputs.items():
        label = str(name).replace("_", " ").title()
        value_text = str(value)
        if value_text.endswith(".html"):
            value_html = f'<a href="{escape(value_text)}">{escape(value_text)}</a>'
        else:
            value_html = f"<code>{escape(value_text)}</code>"
        items.append(f"<li>{escape(label)}: {value_html}</li>")
    return "".join(items)


def build_review_markdown(review: dict, recipe: dict | None = None, matches: dict | None = None) -> str:
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
    if outputs.get("reference_comparison"):
        lines.extend(
            [
                "## Visual comparison",
                "The same number of relative storyboard samples are shown for the reference and the remix.",
                f"- Reference vs remix: {outputs['reference_comparison']}",
                "",
            ]
        )
    if outputs.get("shot_contact_sheet"):
        lines.extend(
            [
                "## Shot timeline",
                "The shot contact sheet shows one labeled frame for every final rendered shot.",
                f"- Shot timeline: {outputs['shot_contact_sheet']}",
                "",
            ]
        )
    lines.extend(_list_section("Failures", list(review.get("failures", []))))
    lines.append("")
    lines.extend(_list_section("Warnings", list(review.get("warnings", []))))
    lines.append("")
    lines.extend(_list_section("Missing segments", list(review.get("missing_segments", []))))
    lines.append("")
    lines.extend(_list_section("Low confidence segments", list(review.get("low_confidence_segments", []))))
    lines.append("")
    lines.extend(_story_support_section(review.get("story_support")))
    lines.append("")
    lines.extend(_storyboard_markdown_section(recipe, matches, review))
    if review.get("visual_selection"):
        lines.append("")
        lines.extend(_visual_selection_markdown_section(review.get("visual_selection")))
    if review.get("shot_plan"):
        lines.append("")
        lines.extend(_shot_plan_markdown_section(review.get("shot_plan")))
    if review.get("change_report"):
        lines.append("")
        lines.extend(_change_report_markdown_section(review.get("change_report")))
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


def write_review_markdown(
    review: dict,
    output_path: Path,
    recipe: dict | None = None,
    matches: dict | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_review_markdown(review, recipe, matches), encoding="utf-8")


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
    story_support = _story_support_html(review.get("story_support"))
    outputs_list = _outputs_html(outputs)
    comparison_section = ""
    if outputs.get("reference_comparison"):
        comparison_section = (
            "<h2>Reference vs Remix</h2>"
            "<p>The same number of relative storyboard samples are shown for the reference and the remix.</p>"
            f'<img alt="reference versus remix comparison" src="{escape(str(outputs["reference_comparison"]))}">'
        )
    shot_contact_section = ""
    if outputs.get("shot_contact_sheet"):
        shot_contact_section = (
            "<h2>Shot Timeline</h2>"
            "<p>One labeled frame per final rendered shot.</p>"
            f'<img alt="shot contact sheet" src="{escape(str(outputs["shot_contact_sheet"]))}">'
        )
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
    .storyboard {{ display: grid; gap: 12px; }}
    .storyboard-row {{ background: #fff; border: 1px solid #d6dae0; padding: 12px; }}
    .storyboard-head {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 6px; }}
    .storyboard-head span {{ color: #5b6470; font-family: Consolas, monospace; }}
    .storyboard-caption {{ margin: 0 0 10px; font-weight: 700; }}
    .storyboard dl {{ display: grid; grid-template-columns: 120px 1fr; gap: 6px 10px; margin: 0; }}
    .storyboard dt {{ color: #5b6470; font-weight: 700; }}
    .storyboard dd {{ margin: 0; overflow-wrap: anywhere; }}
    figure {{ margin: 0; }}
    figcaption {{ margin-top: 6px; color: #5b6470; overflow-wrap: anywhere; }}
    .risk-warning {{ border-left: 4px solid #b45309; }}
    .risk-none {{ border-left: 4px solid #2f855a; }}
    .visual-selection-frames {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .visual-selection-frames img {{ width: 120px; max-height: 240px; object-fit: contain; }}
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
  {shot_contact_section}
  {comparison_section}
  <h2>Outputs</h2>
  <ul>{outputs_list}</ul>
  <h2>Warnings</h2>
  <ul>{warnings}</ul>
  <h2>Failures</h2>
  <ul>{failures}</ul>
  <h2>Story support</h2>
  <ul>{story_support}</ul>
  <h2>Storyboard</h2>
  <section class="storyboard">{_storyboard_html(recipe, matches, review)}</section>
  {_visual_selection_section_html(review.get('visual_selection'))}
  {_shot_plan_html(review.get('shot_plan'))}
  {_change_report_section_html(review.get('change_report'))}
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
    change_report = html_review.get("change_report")
    if isinstance(change_report, dict):
        for item in change_report.get("changed_segments", []):
            if isinstance(item, dict):
                _relativize_change_frame(item, "before_frame", base_dir)
                _relativize_change_frame(item, "after_frame", base_dir)
    visual_selection = html_review.get("visual_selection")
    if isinstance(visual_selection, dict):
        for key in ("candidate_sheet",):
            _relativize_visual_path(visual_selection, key, base_dir)
        for item in visual_selection.get("selections", []):
            if isinstance(item, dict):
                frames = item.get("frames", [])
                if isinstance(frames, list):
                    item["frames"] = [_relative_path(value, base_dir) for value in frames]
                final_frames = item.get("final_frames", [])
                if isinstance(final_frames, list):
                    item["final_frames"] = [_relative_path(value, base_dir) for value in final_frames]
    return html_review


def _visual_selection_section_html(visual_selection: dict | None) -> str:
    if not visual_selection:
        return ""
    return f"<h2>Visual selection</h2><section>{_visual_selection_html(visual_selection)}</section>"


def _relativize_visual_path(data: dict, key: str, base_dir: Path) -> None:
    value = data.get(key)
    if isinstance(value, str) and value:
        data[key] = _relative_path(value, base_dir)


def _relative_path(value: object, base_dir: Path) -> str:
    if not isinstance(value, str) or not value:
        return str(value or "")
    try:
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate.resolve().relative_to(base_dir.resolve()).as_posix()
    except (OSError, ValueError):
        pass
    return value


def _relativize_change_frame(item: dict, key: str, base_dir: Path) -> None:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        return
    try:
        candidate = Path(value)
        if candidate.is_absolute():
            item[key] = candidate.resolve().relative_to(base_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return
