from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jianji_flow import __version__
from jianji_flow.contracts import validate_manifest, validate_matches, validate_recipe
from jianji_flow.matcher import build_recipe, match_segments
from jianji_flow.media_probe import run_ffprobe
from jianji_flow.media_scan import scan_assets, write_manifest
from jianji_flow.paths import make_output_dir, resolve_existing_dir, resolve_existing_file
from jianji_flow.planner import build_segment_plan
from jianji_flow.render import render_preview
from jianji_flow.review import build_review, write_review_markdown
from jianji_flow.semantics import validate_semantics
from jianji_flow.subtitles import write_srt


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
    return parser


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_script(path_text: str | None) -> str | None:
    if path_text is None:
        return None
    return resolve_existing_file(path_text).read_text(encoding="utf-8")


def _run_pipeline(args: argparse.Namespace) -> int:
    try:
        work_dir = make_output_dir(Path(args.work_dir).resolve().parent, Path(args.work_dir).name)
        remix_path = work_dir / "remix.mp4"
        if remix_path.exists():
            remix_path.unlink()

        reference_path = resolve_existing_file(args.reference)
        asset_root = resolve_existing_dir(args.assets)
        script_text = _read_script(args.script)

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
            audio_strategy="silent-preview",
        )
        validate_matches(matches)
        validate_recipe(recipe)

        matches_path = work_dir / "matches.json"
        recipe_path = work_dir / "recipe.json"
        captions_path = work_dir / "captions.srt"
        review_path = work_dir / "review.md"
        _write_json(matches_path, matches)
        _write_json(recipe_path, recipe)
        write_srt(recipe, captions_path)

        semantic_errors = validate_semantics(recipe, matches, manifest, str(reference_path), str(asset_root), str(work_dir))
        if semantic_errors:
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

        render_preview(
            recipe_path,
            matches_path,
            manifest_path,
            remix_path,
            work_dir=work_dir,
            reference_path=reference_path,
            asset_root=asset_root,
        )
        review = build_review(recipe, matches, remix_path, captions_path)
        review["outputs"]["manifest"] = manifest_path.as_posix()
        review["outputs"]["recipe"] = recipe_path.as_posix()
        review["outputs"]["matches"] = matches_path.as_posix()
        write_review_markdown(review, review_path)
        print(f"jianji-flow completed: {review_path}")
        return 0 if review["status"] in {"pass", "warning"} else 1
    except Exception as exc:
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
    if args.command == "run":
        return _run_pipeline(args)
    return 0
