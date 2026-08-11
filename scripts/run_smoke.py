from __future__ import annotations

import shutil
import os
from pathlib import Path

from jianji_flow.cli import main as cli_main
from jianji_flow.media_probe import run_ffprobe

from generate_fixtures import generate_fixtures


ROOT = Path(__file__).resolve().parents[1]


def _assert_outputs(work_dir: Path) -> None:
    for name in (
        "manifest.json",
        "recipe.json",
        "matches.json",
        "captions.srt",
        "captions.ass",
        "voiceover.wav",
        "remix.mp4",
        "contact-sheet.png",
        "review.md",
        "review.html",
    ):
        path = work_dir / name
        if not path.exists():
            raise AssertionError(f"missing smoke output: {path}")
    info = run_ffprobe(work_dir / "remix.mp4")
    if info.duration_ms <= 0:
        raise AssertionError(f"invalid smoke remix duration: {work_dir / 'remix.mp4'}")
    if not info.has_audio:
        raise AssertionError(f"smoke remix has no audio: {work_dir / 'remix.mp4'}")


def _run_case(mode: str, scenario: str, script_name: str, fixture_root: Path, run_root: Path) -> None:
    work_dir = run_root / scenario
    code = cli_main(
        [
            "run",
            "--mode",
            mode,
            "--reference",
            str(fixture_root / scenario / "reference.mp4"),
            "--assets",
            str(fixture_root / scenario / "assets"),
            "--script",
            str(fixture_root / scenario / script_name),
            "--work-dir",
            str(work_dir),
            "--target-width",
            "320",
            "--target-height",
            "180",
            "--target-fps",
            "12",
        ]
    )
    if code != 0:
        raise AssertionError(f"smoke case failed: {scenario}")
    _assert_outputs(work_dir)


def main() -> int:
    smoke_root = ROOT / "out" / f"smoke-{os.getpid()}"
    if smoke_root.exists():
        shutil.rmtree(smoke_root)
    smoke_root.mkdir(parents=True, exist_ok=True)
    fixture_root = smoke_root / "fixtures"
    generate_fixtures(fixture_root)

    _run_case("product", "scenario-a-product", "script.txt", fixture_root, smoke_root)
    _run_case("talking-head", "scenario-b-talking", "transcript.txt", fixture_root, smoke_root)
    print("smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
