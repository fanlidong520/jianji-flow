from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from jsonschema.exceptions import ValidationError

from jianji_flow import __version__
from jianji_flow.asset_diagnosis import diagnose_product_assets, format_asset_diagnosis
from jianji_flow.candidate_review import write_candidate_review
from jianji_flow.change_report import build_change_report
from jianji_flow.contact_sheet import (
    write_contact_sheet,
    write_reference_comparison_sheet,
    write_shot_contact_sheet,
)
from jianji_flow.contracts import validate_fixes, validate_manifest, validate_matches, validate_recipe
from jianji_flow.environment import check_environment, format_environment_report
from jianji_flow.fixtures import generate_fixtures
from jianji_flow.fixes import build_fixes_template, build_recommended_fixes
from jianji_flow.matcher import apply_match_overrides, build_recipe, match_segments, retime_recipe_and_matches
from jianji_flow.media_probe import run_ffprobe
from jianji_flow.media_scan import scan_assets, write_manifest
from jianji_flow.paths import make_output_dir, resolve_existing_dir, resolve_existing_file
from jianji_flow.planner import build_segment_plan
from jianji_flow.quality_diagnosis import diagnose_source_matches
from jianji_flow.quickstart import default_product_script, default_quick_work_dir
from jianji_flow.render import render_preview
from jianji_flow.review import build_review, write_review_html, write_review_markdown
from jianji_flow.review_summary import build_review_summary
from jianji_flow.semantics import validate_semantics
from jianji_flow.shot_detection import build_multi_shot_matches, synchronize_shot_plan
from jianji_flow.source_diversity import diagnose_source_diversity
from jianji_flow.subtitles import write_ass, write_srt
from jianji_flow.visual_similarity import is_visually_similar
from jianji_flow.visual_candidates import (
    apply_visual_selections,
    build_visual_candidate_manifest,
    load_visual_selection,
    write_final_visual_selection_frames,
    write_visual_candidate_artifacts,
)
from jianji_flow.voiceover import create_voiceover, probe_voiceover, validate_voiceover
from jianji_flow.window_scoring import score_source_window


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jianji-flow")
    parser.add_argument("--version", action="version", version=f"jianji-flow {__version__}")

    commands = parser.add_subparsers(dest="command")
    run = commands.add_parser("run", help="parse a remix run request")
    run.add_argument("--mode", choices=("product", "talking-head"), required=True)
    run.add_argument("--reference", required=True)
    run.add_argument("--assets", required=True)
    run.add_argument("--work-dir", required=True)
    run.add_argument("--script")
    run.add_argument("--fixes", help="optional JSON file that pins selected segments or roles to replacement assets")
    run.add_argument("--apply-recommendation", help="apply a clean recommended fix from --fixes for one segment id")
    run.add_argument("--visual-selections", help="optional Codex visual selection JSON file")
    run.add_argument("--multi-shot", action="store_true", help="split selected windows at detected scene boundaries")
    run.add_argument("--confidence-threshold", type=float)
    run.add_argument("--target-width", type=int)
    run.add_argument("--target-height", type=int)
    run.add_argument("--target-fps", type=float)

    doctor = commands.add_parser("doctor", help="check local environment")
    doctor.add_argument("--work-dir")

    demo = commands.add_parser("demo", help="run a local generated product demo")
    demo.add_argument("--work-dir")
    demo.add_argument("--target-width", type=int)
    demo.add_argument("--target-height", type=int)
    demo.add_argument("--target-fps", type=float)

    quick = commands.add_parser("quick", help="run the shortest home-product draft flow")
    quick.add_argument("--reference", required=True)
    quick.add_argument("--assets", required=True)
    quick.add_argument("--script")
    quick.add_argument("--fixes", help="optional JSON file that pins selected segments or roles to replacement assets")
    quick.add_argument("--apply-recommendation", help="apply a clean recommended fix from --fixes for one segment id")
    quick.add_argument("--visual-selections", help="optional Codex visual selection JSON file")
    quick.add_argument("--multi-shot", action="store_true", help="split selected windows at detected scene boundaries")
    quick.add_argument("--work-dir")
    quick.add_argument("--mode", choices=("product", "talking-head"), default="product")
    quick.add_argument("--confidence-threshold", type=float)
    quick.add_argument("--target-width", type=int)
    quick.add_argument("--target-height", type=int)
    quick.add_argument("--target-fps", type=float)

    visual_review = commands.add_parser("visual-review", help="build a visual candidate board without rendering")
    visual_review.add_argument("--reference", required=True)
    visual_review.add_argument("--assets", required=True)
    visual_review.add_argument("--work-dir", required=True)
    visual_review.add_argument("--script")
    visual_review.add_argument("--mode", choices=("product", "talking-head"), default="product")
    return parser


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_script(path_text: str | None) -> str | None:
    if path_text is None:
        return None
    return resolve_existing_file(path_text).read_text(encoding="utf-8")


def _read_fixes(path_text: str | None, *, apply_recommendation: str | None = None) -> dict | None:
    if path_text is None:
        if apply_recommendation:
            raise ValueError("--apply-recommendation requires --fixes")
        return None
    path = resolve_existing_file(path_text)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"fixes file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"fixes file must contain a JSON object: {path}")
    try:
        validate_fixes(data)
    except ValidationError as exc:
        error_path = ".".join(str(part) for part in exc.absolute_path)
        location = f" at {error_path}" if error_path else ""
        raise ValueError(f"fixes file schema error{location}: {exc.message}") from exc
    if apply_recommendation:
        data = build_recommended_fixes(data, apply_recommendation)
        validate_fixes(data)
    return data


def _read_visual_selection_input(
    path_text: str | None,
) -> tuple[dict, dict, Path, Path] | None:
    if path_text is None:
        return None
    selection_path = resolve_existing_file(path_text)
    selection = load_visual_selection(selection_path)
    manifest_reference = Path(str(selection["candidate_manifest"]))
    manifest_path = manifest_reference if manifest_reference.is_absolute() else selection_path.parent / manifest_reference
    if not manifest_path.exists():
        raise ValueError(f"visual candidate manifest not found: {manifest_path}")
    try:
        candidate_manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"visual candidate manifest is not valid JSON: {manifest_path}: {exc}") from exc
    if not isinstance(candidate_manifest, dict) or not isinstance(candidate_manifest.get("candidates"), list):
        raise ValueError(f"visual candidate manifest is invalid: {manifest_path}")
    return selection, candidate_manifest, selection_path, manifest_path


def _visual_selection_review_data(selection: dict, candidate_manifest: dict, manifest_path: Path) -> dict:
    candidate_by_id = {str(item.get("candidate_id")): item for item in candidate_manifest.get("candidates", [])}
    selections = []
    for segment_id, entry in selection.get("selections", {}).items():
        candidate = candidate_by_id.get(str(entry.get("candidate_id")))
        if candidate is None:
            continue
        frames = [
            (manifest_path.parent / str(frame.get("path", ""))).as_posix()
            for frame in candidate.get("frames", [])
        ]
        selections.append(
            {
                "segment_id": str(segment_id),
                "candidate_id": str(entry.get("candidate_id", "")),
                "reviewer": str(entry.get("reviewer", "")),
                "reason": str(entry.get("reason", "")),
                "asset_path": str(candidate.get("asset_path", "")),
                "source_range": f"{candidate.get('source_start_ms', '')}-{candidate.get('source_end_ms', '')}ms",
                "frames": frames,
            }
        )
    return {
        "candidate_sheet": (manifest_path.parent / "visual-candidate-sheet.png").as_posix(),
        "selections": selections,
    }


def _materialize_visual_selection_review_data(
    selection: dict,
    candidate_manifest: dict,
    manifest_path: Path,
    work_dir: Path,
) -> dict:
    review_data = _visual_selection_review_data(selection, candidate_manifest, manifest_path)
    evidence_dir = work_dir / "visual-selection-evidence"
    if evidence_dir.exists():
        shutil.rmtree(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    candidate_sheet = Path(review_data["candidate_sheet"])
    if not candidate_sheet.exists():
        raise ValueError(
            f"visual candidate sheet missing: {candidate_sheet}; rerun `jianji-flow visual-review` "
            "and use the fresh selection file"
        )
    copied_sheet = evidence_dir / "visual-candidate-sheet.png"
    shutil.copy2(candidate_sheet, copied_sheet)
    review_data["candidate_sheet"] = copied_sheet.as_posix()
    for item in review_data.get("selections", []):
        copied_frames = []
        for index, frame_text in enumerate(item.get("frames", []), start=1):
            frame_path = Path(frame_text)
            if not frame_path.exists():
                continue
            copied_frame = evidence_dir / f"{item['segment_id']}-{index:02d}.png"
            shutil.copy2(frame_path, copied_frame)
            copied_frames.append(copied_frame.as_posix())
        item["frames"] = copied_frames
    return review_data


def _write_visual_board(segments: list[dict], records: list, work_dir: Path) -> dict[str, str]:
    manifest = build_visual_candidate_manifest(segments, records, work_dir)
    return write_visual_candidate_artifacts(manifest, segments, work_dir)


def _visual_board_diagnosis_text(outputs: dict[str, str]) -> str:
    return "\n".join(
        [
            "",
            "## Visual candidate review",
            "Candidate frames were generated without using filename role labels.",
            f"- Candidate sheet: {outputs.get('visual_candidate_sheet', '')}",
            f"- Selection template: {outputs.get('visual_selection_template', '')}",
            "- Next: Codex must inspect the candidate sheet, write candidate_id and reason for genuinely supported segments, then rerun with --visual-selections; do not ask the user to edit JSON.",
            "- Local frame quality metrics are not semantic proof; publishing still requires human review.",
            "",
        ]
    )


def _success_artifact_names() -> tuple[str, ...]:
    return (
        "remix.mp4",
        "voiceover.wav",
        "captions.ass",
        "contact-sheet.png",
        "shot-contact-sheet.png",
        "reference-comparison.png",
        "shot-plan.json",
        "candidate-review.html",
        "fixes.template.json",
        "review.html",
    )


def _run_diagnostic_dir_names() -> tuple[str, ...]:
    return ("visual-similarity-diagnostics", "change-diagnostics", "visual-selection-evidence")


def _success_artifact_dir_names() -> tuple[str, ...]:
    return ("candidate-frames",)


def _run_state_artifact_names() -> tuple[str, ...]:
    return (
        "review.md",
        "review.html",
        "manifest.json",
        "recipe.json",
        "matches.json",
        "captions.srt",
        "captions.ass",
        "voiceover.wav",
        "remix.mp4",
        "contact-sheet.png",
        "shot-contact-sheet.png",
        "reference-comparison.png",
        "shot-plan.json",
        "candidate-review.html",
        "fixes.template.json",
    )


def _clear_success_artifacts(work_dir: Path, *, keep_diagnostics: bool = False) -> None:
    diagnostic_names = {"contact-sheet.png", "shot-contact-sheet.png"} if keep_diagnostics else set()
    for name in _success_artifact_names():
        if name in diagnostic_names:
            continue
        path = work_dir / name
        if path.exists():
            path.unlink()
    if not keep_diagnostics:
        _clear_run_diagnostic_dirs(work_dir)
    for name in _success_artifact_dir_names():
        path = work_dir / name
        if path.exists():
            shutil.rmtree(path)


def _clear_run_diagnostic_dirs(work_dir: Path) -> None:
    for name in _run_diagnostic_dir_names():
        path = work_dir / name
        if path.exists():
            shutil.rmtree(path)


def _clear_run_state_artifacts(work_dir: Path) -> None:
    for name in _run_state_artifact_names():
        path = work_dir / name
        if path.exists():
            path.unlink()


def _write_failure_review(work_dir: Path, failure: str) -> None:
    review_path = work_dir / "review.md"
    review = {
        "status": "fail",
        "failures": [failure],
        "warnings": [],
        "missing_segments": [],
        "low_confidence_segments": [],
        "outputs": {},
    }
    write_review_markdown(review, review_path)


def _write_diagnosis(work_dir: Path, text: str) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / "diagnosis.md"
    path.write_text(text, encoding="utf-8")
    return path


def _source_preflight_diagnosis_text(source_preflight: dict) -> str:
    failures = list(source_preflight.get("failures", []))
    warnings = list(source_preflight.get("warnings", []))
    if not failures and not warnings:
        return ""

    lines = ["", "## Source preflight", "Source frame screening before voiceover and rendering.", ""]
    lines.extend(f"- FAIL - {failure}" for failure in failures)
    lines.extend(f"- WARNING - {warning}" for warning in warnings)
    diagnostics_dir = source_preflight.get("diagnostics_dir")
    if diagnostics_dir:
        lines.append(f"- Diagnostics: `{diagnostics_dir}`")
    lines.append("")
    lines.append("Replace source clips with platform UI, old subtitles, or damaged frames before publishing.")
    return "\n".join(lines) + "\n"


def _append_existing_diagnosis(work_dir: Path, text: str) -> Path | None:
    if not text:
        return None
    path = work_dir / "diagnosis.md"
    if not path.exists():
        return None
    existing = path.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n") else "\n"
    path.write_text(existing + separator + text, encoding="utf-8")
    return path


def _apply_source_preflight_evidence(matches: dict, clean_segment_ids: list[str]) -> dict:
    clean_ids = {str(segment_id) for segment_id in clean_segment_ids}
    if not clean_ids:
        return matches
    updated = []
    for match in matches.get("matches", []):
        if str(match.get("segment_id")) in clean_ids and match.get("status") in {"selected", "low_confidence"}:
            evidence = list(match.get("evidence", []))
            if "source-preflight:clean" not in evidence:
                evidence.append("source-preflight:clean")
            updated.append({**match, "evidence": evidence})
        else:
            updated.append(dict(match))
    return {**matches, "matches": updated}


def _remove_success_outputs_from_review(review: dict, *, keep_diagnostics: bool = False) -> None:
    outputs = review.get("outputs", {})
    removable_outputs = [
        "remix",
        "voiceover",
        "captions_ass",
        "fixes_template",
        "candidate_review",
        "candidate_frames",
        "review_html",
        "reference_comparison",
        "shot_plan",
    ]
    if not keep_diagnostics:
        removable_outputs.append("contact_sheet")
    for name in removable_outputs:
        outputs.pop(name, None)


def _minimum_viable_voiceover_duration_ms(segment_count: int) -> int:
    return max(1000, segment_count * 250)


def _build_window_scorer(work_dir: Path):
    diagnostics_dir = work_dir / "window-diagnostics"

    def scorer(asset, start_ms: int, end_ms: int) -> float:
        return score_source_window(Path(str(asset.path)), start_ms, end_ms, diagnostics_dir)

    return scorer


def _build_visual_similarity_checker(work_dir: Path):
    diagnostics_dir = work_dir / "visual-similarity-diagnostics"

    def checker(
        current_path: str,
        candidate_path: str,
        segment_duration_ms: int,
        current_start_ms: int,
        candidate_start_ms: int,
    ) -> bool:
        return is_visually_similar(
            Path(current_path),
            Path(candidate_path),
            duration_ms=segment_duration_ms,
            diagnostics_dir=diagnostics_dir,
            left_start_ms=current_start_ms,
            right_start_ms=candidate_start_ms,
        )

    return checker


def _run_pipeline(args: argparse.Namespace, *, script_text_override: str | None = None) -> int:
    work_dir: Path | None = None
    try:
        visual_selection_input = _read_visual_selection_input(getattr(args, "visual_selections", None))
        work_dir = make_output_dir(Path(args.work_dir).resolve().parent, Path(args.work_dir).name)
        _clear_success_artifacts(work_dir)
        remix_path = work_dir / "remix.mp4"

        reference_path = resolve_existing_file(args.reference)
        asset_root = resolve_existing_dir(args.assets)
        script_text = script_text_override if script_text_override is not None else _read_script(args.script)

        reference_info = run_ffprobe(reference_path)
        target = {
            "width": args.target_width or reference_info.width,
            "height": args.target_height or reference_info.height,
            "fps": args.target_fps or reference_info.fps or 30,
        }
        records = scan_assets(asset_root)
        manifest_path = work_dir / "manifest.json"
        write_manifest(records, manifest_path, asset_root=asset_root, reference_path=reference_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_manifest(manifest)

        segments = build_segment_plan(args.mode, reference_info.duration_ms, script_text)
        window_scorer = _build_window_scorer(work_dir)
        matches = match_segments(
            segments,
            records,
            threshold=args.confidence_threshold or 0.6,
            window_scorer=window_scorer,
        )
        base_matches_for_change_report = matches
        fixes_data = _read_fixes(args.fixes, apply_recommendation=args.apply_recommendation)
        matches = apply_match_overrides(
            segments,
            matches,
            records,
            fixes_data,
            window_scorer=window_scorer,
        )
        if visual_selection_input is not None:
            selection, candidate_manifest, selection_path, candidate_manifest_path = visual_selection_input
            matches = apply_visual_selections(segments, matches, records, selection, candidate_manifest)
            visual_selection_review = _materialize_visual_selection_review_data(
                selection,
                candidate_manifest,
                candidate_manifest_path,
                work_dir,
            )
        else:
            selection_path = None
            candidate_manifest_path = None
            visual_selection_review = None
        shot_plan = None
        if getattr(args, "multi_shot", False):
            matches, shot_plan = build_multi_shot_matches(segments, matches)
        change_requested = fixes_data is not None or visual_selection_input is not None
        recipe = build_recipe(
            args.mode,
            target,
            segments,
            matches,
            output_path=work_dir / "remix.mp4",
            audio_strategy="voiceover-only",
            voiceover_path=work_dir / "voiceover.wav",
            caption_burn_in=True,
        )
        validate_matches(matches)
        validate_recipe(recipe)
        pretime_recipe = recipe

        matches_path = work_dir / "matches.json"
        recipe_path = work_dir / "recipe.json"
        captions_path = work_dir / "captions.srt"
        ass_path = work_dir / "captions.ass"
        voiceover_path = work_dir / "voiceover.wav"
        contact_sheet_path = work_dir / "contact-sheet.png"
        shot_contact_sheet_path = work_dir / "shot-contact-sheet.png"
        reference_comparison_path = work_dir / "reference-comparison.png"
        shot_plan_path = work_dir / "shot-plan.json"
        source_diagnostics_dir = work_dir / "source-diagnostics"
        review_path = work_dir / "review.md"
        review_html_path = work_dir / "review.html"
        fixes_template_path = work_dir / "fixes.template.json"
        candidate_review_path = work_dir / "candidate-review.html"
        candidate_frames_dir = work_dir / "candidate-frames"
        _write_json(matches_path, matches)
        if shot_plan is not None:
            _write_json(shot_plan_path, shot_plan)
        _write_json(recipe_path, recipe)
        write_srt(recipe, captions_path)
        write_ass(recipe, ass_path)

        semantic_errors = validate_semantics(recipe, matches, manifest, str(reference_path), str(asset_root), str(work_dir))
        if semantic_errors:
            _clear_success_artifacts(work_dir)
            review = {
                "status": "fail",
                "failures": semantic_errors,
                "warnings": [],
                "missing_segments": [],
                "low_confidence_segments": [],
                "outputs": {
                    "manifest": manifest_path.as_posix(),
                    "recipe": recipe_path.as_posix(),
                    "matches": matches_path.as_posix(),
                    "captions": captions_path.as_posix(),
                },
            }
            write_review_markdown(review, review_path, recipe, matches)
            print(f"validation failed; review written to {review_path}", file=sys.stderr)
            return 1

        source_identity = {}
        for asset in manifest.get("assets", []):
            path_text = str(asset.get("path", "")).strip()
            sha256 = str(asset.get("sha256", "")).strip()
            if path_text and sha256:
                source_identity[Path(path_text).resolve().as_posix().casefold()] = sha256
        source_preflight = diagnose_source_matches(
            recipe,
            matches,
            source_diagnostics_dir,
            source_identity=source_identity,
        )
        matches = _apply_source_preflight_evidence(matches, source_preflight.get("clean_segment_ids", []))
        _write_json(matches_path, matches)
        _append_existing_diagnosis(work_dir, _source_preflight_diagnosis_text(source_preflight))
        if source_preflight["status"] == "fail":
            _clear_success_artifacts(work_dir)
            review = {
                "status": "fail",
                "failures": source_preflight["failures"],
                "warnings": source_preflight["warnings"],
                "missing_segments": [],
                "low_confidence_segments": [],
                "outputs": {
                    "manifest": manifest_path.as_posix(),
                    "recipe": recipe_path.as_posix(),
                    "matches": matches_path.as_posix(),
                    "captions": captions_path.as_posix(),
                    "source_diagnostics": source_preflight["diagnostics_dir"],
                },
            }
            write_review_markdown(review, review_path, recipe, matches)
            print(f"source preflight failed; review written to {review_path}", file=sys.stderr)
            return 1

        create_voiceover(recipe, voiceover_path)
        validate_voiceover(voiceover_path)
        voiceover_duration_ms = probe_voiceover(voiceover_path).duration_ms
        minimum_voiceover_ms = _minimum_viable_voiceover_duration_ms(len(recipe.get("segments", [])))
        if voiceover_duration_ms < minimum_voiceover_ms:
            raise ValueError(
                f"voiceover duration {voiceover_duration_ms}ms is too short for "
                f"{len(recipe.get('segments', []))} segments"
            )
        recipe, matches = retime_recipe_and_matches(recipe, matches, voiceover_duration_ms)
        if shot_plan is not None:
            shot_plan = synchronize_shot_plan(shot_plan, matches)
        if visual_selection_review is not None:
            visual_selection_review = write_final_visual_selection_frames(
                visual_selection_review,
                matches,
                work_dir,
            )
        if change_requested:
            _, base_matches_for_change_report = retime_recipe_and_matches(
                pretime_recipe,
                base_matches_for_change_report,
                voiceover_duration_ms,
            )
        validate_voiceover(voiceover_path, expected_duration_ms=int(recipe["duration_ms"]))
        semantic_errors = validate_semantics(recipe, matches, manifest, str(reference_path), str(asset_root), str(work_dir))
        if semantic_errors:
            _clear_success_artifacts(work_dir)
            review = {
                "status": "fail",
                "failures": semantic_errors,
                "warnings": [],
                "missing_segments": [],
                "low_confidence_segments": [],
                "outputs": {
                    "manifest": manifest_path.as_posix(),
                    "recipe": recipe_path.as_posix(),
                    "matches": matches_path.as_posix(),
                    "captions": captions_path.as_posix(),
                },
            }
            write_review_markdown(review, review_path, recipe, matches)
            print(f"validation failed after voiceover retiming; review written to {review_path}", file=sys.stderr)
            return 1
        _write_json(matches_path, matches)
        _write_json(recipe_path, recipe)
        if shot_plan is not None:
            _write_json(shot_plan_path, shot_plan)
        write_srt(recipe, captions_path)
        write_ass(recipe, ass_path)

        render_preview(
            recipe_path,
            matches_path,
            manifest_path,
            remix_path,
            work_dir=work_dir,
            reference_path=reference_path,
            asset_root=asset_root,
            captions_path=ass_path,
            voiceover_path=voiceover_path,
        )
        write_contact_sheet(remix_path, contact_sheet_path, recipe=recipe)
        if shot_plan is not None:
            write_shot_contact_sheet(
                remix_path,
                shot_contact_sheet_path,
                recipe=recipe,
                matches=matches,
            )
        write_reference_comparison_sheet(
            reference_path,
            remix_path,
            reference_comparison_path,
            recipe=recipe,
        )
        review = build_review(
            recipe,
            matches,
            remix_path,
            captions_path,
            ass_path=ass_path,
            voiceover_path=voiceover_path,
            contact_sheet_path=contact_sheet_path,
            shot_contact_sheet_path=shot_contact_sheet_path if shot_plan is not None else None,
            reference_comparison_path=reference_comparison_path,
            shot_plan=shot_plan,
            review_html_path=review_html_path,
            visual_selection=visual_selection_review,
        )
        if change_requested:
            change_diagnostics_dir = work_dir / "change-diagnostics"
            review["change_report"] = build_change_report(
                recipe,
                base_matches_for_change_report,
                matches,
                diagnostics_dir=change_diagnostics_dir,
            )
            if change_diagnostics_dir.exists() and any(change_diagnostics_dir.glob("*.png")):
                review["outputs"]["change_diagnostics"] = change_diagnostics_dir.as_posix()
        review["outputs"]["manifest"] = manifest_path.as_posix()
        review["outputs"]["recipe"] = recipe_path.as_posix()
        review["outputs"]["matches"] = matches_path.as_posix()
        review["outputs"]["captions_ass"] = ass_path.as_posix()
        if selection_path is not None and candidate_manifest_path is not None:
            review["outputs"]["visual_selections"] = selection_path.as_posix()
            review["outputs"]["visual_candidate_manifest"] = candidate_manifest_path.as_posix()
            if visual_selection_review and visual_selection_review.get("candidate_sheet"):
                review["outputs"]["visual_candidate_sheet"] = visual_selection_review["candidate_sheet"]
        if shot_plan is not None:
            review["outputs"]["shot_plan"] = shot_plan_path.as_posix()
            review["outputs"]["shot_contact_sheet"] = shot_contact_sheet_path.as_posix()
        fixes_template = build_fixes_template(
            recipe,
            matches,
            records,
            review,
            minimum_duration_recipe=pretime_recipe,
            visual_similarity_checker=_build_visual_similarity_checker(work_dir),
        )
        _write_json(fixes_template_path, fixes_template)
        review["outputs"]["fixes_template"] = fixes_template_path.as_posix()
        review["outputs"].update(
            write_candidate_review(
                recipe,
                matches,
                fixes_template,
                candidate_review_path,
                frames_dir=candidate_frames_dir,
            )
        )
        visual_similarity_diagnostics = work_dir / "visual-similarity-diagnostics"
        if visual_similarity_diagnostics.exists() and any(visual_similarity_diagnostics.glob("*.png")):
            review["outputs"]["visual_similarity_diagnostics"] = visual_similarity_diagnostics.as_posix()
        if source_preflight["status"] == "warning":
            review["warnings"].extend(source_preflight["warnings"])
            review["outputs"]["source_diagnostics"] = source_preflight["diagnostics_dir"]
            review["status"] = "fail" if review["failures"] else "warning"
            review["summary"] = build_review_summary(review)
        if review["status"] == "fail":
            _clear_success_artifacts(work_dir, keep_diagnostics=True)
            _remove_success_outputs_from_review(review, keep_diagnostics=True)
            write_review_markdown(review, review_path, recipe, matches)
            print(f"jianji-flow failed review: {review_path}", file=sys.stderr)
            return 1
        write_review_markdown(review, review_path, recipe, matches)
        write_review_html(review, recipe, matches, review_html_path)
        if review["status"] == "warning":
            print(f"jianji-flow review required: {review_path}")
        else:
            print(f"jianji-flow passed review: {review_path}")
        return 0 if review["status"] in {"pass", "warning"} else 1
    except Exception as exc:
        if work_dir is not None:
            _clear_success_artifacts(work_dir)
            _write_failure_review(work_dir, str(exc))
        print(f"jianji-flow failed: {exc}", file=sys.stderr)
        return 1


def _run_demo_command(args: argparse.Namespace) -> int:
    work_dir = Path(args.work_dir).resolve() if args.work_dir else default_quick_work_dir(Path.cwd())
    try:
        fixture_root = work_dir.parent / f"{work_dir.name}-fixtures"
        generate_fixtures(fixture_root)
        demo_args = argparse.Namespace(
            command="run",
            mode="product",
            reference=str(fixture_root / "scenario-a-product" / "reference.mp4"),
            assets=str(fixture_root / "scenario-a-product" / "assets"),
            script=str(fixture_root / "scenario-a-product" / "script.txt"),
            work_dir=str(work_dir),
            fixes=None,
            apply_recommendation=None,
            visual_selections=None,
            confidence_threshold=None,
            target_width=args.target_width,
            target_height=args.target_height,
            target_fps=args.target_fps,
        )
        return _run_pipeline(demo_args)
    except Exception as exc:
        work_dir.mkdir(parents=True, exist_ok=True)
        _clear_run_state_artifacts(work_dir)
        _write_failure_review(work_dir, str(exc))
        print(f"jianji-flow failed: {exc}", file=sys.stderr)
        return 1


def _run_visual_review_command(args: argparse.Namespace) -> int:
    work_dir = Path(args.work_dir).resolve()
    try:
        work_dir = make_output_dir(work_dir.parent, work_dir.name)
        reference_path = resolve_existing_file(args.reference)
        asset_root = resolve_existing_dir(args.assets)
        script_text = _read_script(args.script) if args.script else (default_product_script() if args.mode == "product" else None)
        reference_info = run_ffprobe(reference_path)
        records = scan_assets(asset_root)
        segments = build_segment_plan(args.mode, reference_info.duration_ms, script_text)
        outputs = _write_visual_board(segments, records, work_dir)
        print(f"jianji-flow visual review board written: {outputs['visual_candidate_sheet']}")
        print(f"selection template: {outputs['visual_selection_template']}")
        return 0
    except Exception as exc:
        work_dir.mkdir(parents=True, exist_ok=True)
        _write_failure_review(work_dir, str(exc))
        print(f"jianji-flow failed: {exc}", file=sys.stderr)
        return 1


def _run_quick_command(args: argparse.Namespace) -> int:
    if not args.work_dir:
        args.work_dir = str(default_quick_work_dir(Path.cwd()))
    if args.mode != "product" and not args.script:
        print("jianji-flow failed: quick --mode talking-head requires --script", file=sys.stderr)
        return 2

    work_dir: Path | None = None
    try:
        script_override = None if args.script else default_product_script()
        work_dir = make_output_dir(Path(args.work_dir).resolve().parent, Path(args.work_dir).name)
        _clear_success_artifacts(work_dir)
        reference_path = resolve_existing_file(args.reference)
        asset_root = resolve_existing_dir(args.assets)
        reference_info = run_ffprobe(reference_path)
        records = scan_assets(asset_root)
        segments = build_segment_plan(args.mode, reference_info.duration_ms, script_override)
        if args.mode == "product":
            visual_selection_supplied = bool(getattr(args, "visual_selections", None))
            asset_inputs = [
                {
                    "asset_id": item.asset_id,
                    "path": item.path.as_posix(),
                    "duration_ms": item.duration_ms,
                    "sha256": item.sha256,
                    "width": item.width,
                    "height": item.height,
                    "fps": item.fps,
                }
                for item in records
            ]
            report = diagnose_product_assets(
                asset_inputs,
                segments,
            )
            source_diversity = diagnose_source_diversity(
                asset_inputs,
                work_dir / "source-diversity-diagnostics",
            )
            report["source_diversity"] = source_diversity
            if source_diversity["status"] == "warning" and report["status"] == "pass":
                report["status"] = "warning"
            diagnosis_path = _write_diagnosis(
                work_dir,
                format_asset_diagnosis(report, visual_selection_supplied=visual_selection_supplied),
            )
            if report["status"] == "fail":
                board_outputs = _write_visual_board(segments, records, work_dir)
                _append_existing_diagnosis(work_dir, _visual_board_diagnosis_text(board_outputs))
                if visual_selection_supplied:
                    return _run_pipeline(args, script_text_override=script_override)
                _clear_run_state_artifacts(work_dir)
                print(f"quick stopped; diagnosis written to {diagnosis_path}", file=sys.stderr)
                return 1
        return _run_pipeline(args, script_text_override=script_override)
    except Exception as exc:
        if work_dir is None:
            work_dir = make_output_dir(Path(args.work_dir).resolve().parent, Path(args.work_dir).name)
        _clear_run_state_artifacts(work_dir)
        _write_failure_review(work_dir, str(exc))
        print(f"jianji-flow failed: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args_list = sys.argv[1:] if argv is None else argv
    if args_list == []:
        parser.print_help()
        return 0

    try:
        args = parser.parse_args(args_list)
    except SystemExit as error:
        return int(error.code)
    if args.command == "doctor":
        output_root = Path(args.work_dir).resolve() if args.work_dir else None
        report = check_environment(output_root=output_root)
        print(format_environment_report(report), end="")
        return 0 if report["status"] == "pass" else 1
    if args.command == "demo":
        return _run_demo_command(args)
    if args.command == "visual-review":
        return _run_visual_review_command(args)
    if args.command == "quick":
        return _run_quick_command(args)
    if args.command == "run":
        return _run_pipeline(args)
    return 0
