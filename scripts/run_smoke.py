from __future__ import annotations

import shutil
from pathlib import Path

from jianji_flow.cli import main as cli_main
from jianji_flow.media_probe import run_ffprobe

from generate_fixtures import generate_fixtures


ROOT = Path(__file__).resolve().parents[1]


def _assert_outputs(work_dir: Path) -> None:
    for name in ("manifest.json", "recipe.json", "matches.json", "captions.srt", "remix.mp4", "review.md"):
        path = work_dir / name
        if not path.exists():
            raise AssertionError(f"missing smoke output: {path}")
    info = run_ffprobe(work_dir / "remix.mp4")
    if info.duration_ms <= 0:
        raise AssertionError(f"invalid smoke remix duration: {work_dir / 'remix.mp4'}")


def _run_case(mode: str, scenario: str, script_name: str) -> None:
    work_dir = ROOT / "out" / f"smoke-{scenario}"
    code = cli_main(
        [
            "run",
            "--mode",
            mode,
            "--reference",
            str(ROOT / "fixtures" / scenario / "reference.mp4"),
            "--assets",
            str(ROOT / "fixtures" / scenario / "assets"),
            "--script",
            str(ROOT / "fixtures" / scenario / script_name),
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
    fixture_root = ROOT / "fixtures"
    generate_fixtures(fixture_root)
    smoke_root = ROOT / "out"
    for old in smoke_root.glob("smoke-*"):
        if old.is_dir():
            shutil.rmtree(old)

    _run_case("product", "scenario-a-product", "script.txt")
    _run_case("talking-head", "scenario-b-talking", "transcript.txt")
    print("smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
