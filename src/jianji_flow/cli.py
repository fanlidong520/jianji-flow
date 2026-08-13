from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jianji_flow import __version__
from jianji_flow.asset_diagnosis import diagnose_product_assets, format_asset_diagnosis
from jianji_flow.contact_sheet import write_contact_sheet
from jianji_flow.contracts import validate_manifest, validate_matches, validate_recipe
from jianji_flow.environment import check_environment, format_environment_report
from jianji_flow.fixtures import generate_fixtures
from jianji_flow.matcher import build_recipe, match_segments, retime_recipe_and_matches
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
from jianji_flow.subtitles import write_ass, write_srt
from jianji_flow.voiceover import create_voiceover, probe_voiceover, validate_voiceover


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
    quick.add_argument("--work-dir")
    quick.add_argument("--mode", choices=("product", "talking-head"), default="product")
    quick.add_argument("--confidence-threshold", type=float)
    quick.add_argument("--target-width", type=int)
    quick.add_argument("--target-height", type=int)
    quick.add_argument("--target-fps", type=float)
    return parser


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_script(path_text: str | None) -> str | None:
    if path_text is None:
        return None
    return resolve_existing_file(path_text).read_text(encoding="utf-8")


def _success_artifact_names() -> tuple[str, ...]:
    return ("remix.mp4", "voiceover.wav", "captions.ass", "contact-sheet.png", "review.html")


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
    )


def _clear_success_artifacts(work_dir: Path, *, keep_diagnostics: bool = False) -> None:
    diagnostic_names = {"contact-sheet.png"} if keep_diagnostics else set()
    for name in _success_artifact_names():
        if name in diagnostic_names:
            continue
        path = work_dir / name
        if path.exists():
            path.unlink()


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


def _remove_success_outputs_from_review(review: dict, *, keep_diagnostics: bool = False) -> None:
    outputs = review.get("outputs", {})
    removable_outputs = ["remix", "voiceover", "captions_ass", "review_html"]
    if not keep_diagnostics:
        removable_outputs.append("contact_sheet")
    for name in removable_outputs:
        outputs.pop(name, None)


def _minimum_viable_voiceover_duration_ms(segment_count: int) -> int:
    return max(1000, segment_count * 250)


def _run_pipeline(args: argparse.Namespace, *, script_text_override: str | None = None) -> int:
    work_dir: Path | None = None
    try:
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
        matches = match_segments(segments, records, threshold=args.confidence_threshold or 0.6)
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

        matches_path = work_dir / "matches.json"
        recipe_path = work_dir / "recipe.json"
        captions_path = work_dir / "captions.srt"
        ass_path = work_dir / "captions.ass"
        voiceover_path = work_dir / "voiceover.wav"
        contact_sheet_path = work_dir / "contact-sheet.png"
        source_diagnostics_dir = work_dir / "source-diagnostics"
        review_path = work_dir / "review.md"
        review_html_path = work_dir / "review.html"
        _write_json(matches_path, matches)
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
            write_review_markdown(review, review_path)
            print(f"validation failed; review written to {review_path}", file=sys.stderr)
            return 1

        source_preflight = diagnose_source_matches(recipe, matches, source_diagnostics_dir)
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
            write_review_markdown(review, review_path)
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
            write_review_markdown(review, review_path)
            print(f"validation failed after voiceover retiming; review written to {review_path}", file=sys.stderr)
            return 1
        _write_json(matches_path, matches)
        _write_json(recipe_path, recipe)
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
        review = build_review(
            recipe,
            matches,
            remix_path,
            captions_path,
            ass_path=ass_path,
            voiceover_path=voiceover_path,
            contact_sheet_path=contact_sheet_path,
            review_html_path=review_html_path,
        )
        review["outputs"]["manifest"] = manifest_path.as_posix()
        review["outputs"]["recipe"] = recipe_path.as_posix()
        review["outputs"]["matches"] = matches_path.as_posix()
        review["outputs"]["captions_ass"] = ass_path.as_posix()
        if source_preflight["status"] == "warning":
            review["warnings"].extend(source_preflight["warnings"])
            review["outputs"]["source_diagnostics"] = source_preflight["diagnostics_dir"]
            review["status"] = "fail" if review["failures"] else "warning"
            review["summary"] = build_review_summary(review)
        if review["status"] == "fail":
            _clear_success_artifacts(work_dir, keep_diagnostics=True)
            _remove_success_outputs_from_review(review, keep_diagnostics=True)
            write_review_markdown(review, review_path)
            print(f"jianji-flow failed review: {review_path}", file=sys.stderr)
            return 1
        write_review_markdown(review, review_path)
        write_review_html(review, recipe, matches, review_html_path)
        print(f"jianji-flow completed: {review_path}")
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
            report = diagnose_product_assets(
                [
                    {"asset_id": item.asset_id, "path": item.path.as_posix(), "duration_ms": item.duration_ms}
                    for item in records
                ],
                segments,
            )
            diagnosis_path = _write_diagnosis(work_dir, format_asset_diagnosis(report))
            if report["status"] == "fail":
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
    if args.command == "quick":
        return _run_quick_command(args)
    if args.command == "run":
        return _run_pipeline(args)
    return 0
