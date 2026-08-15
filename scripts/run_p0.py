from __future__ import annotations

import shutil
import os
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from jianji_flow.cli import main as cli_main

from generate_fixtures import generate_fixtures


ROOT = Path(__file__).resolve().parents[1]


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _run(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli_main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def _assert_no_remix(work_dir: Path) -> None:
    for name in ("remix.mp4", "voiceover.wav", "captions.ass", "contact-sheet.png"):
        if (work_dir / name).exists():
            raise AssertionError(f"blocking failure produced stale success artifact {name}: {work_dir}")
    if not (work_dir / "review.html").exists():
        raise AssertionError(f"blocking failure did not produce review.html: {work_dir}")


def test_missing_reference(base: Path, fixture_root: Path) -> None:
    work_dir = base / "missing-reference"
    code, _, stderr = _run(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            str(base / "missing.mp4"),
            "--assets",
            str(fixture_root / "scenario-a-product" / "assets"),
            "--work-dir",
            str(work_dir),
        ]
    )
    if code == 0:
        raise AssertionError("missing reference should fail")
    if "failed" not in stderr.lower():
        raise AssertionError("missing reference did not report failure")
    _assert_no_remix(work_dir)


def test_empty_asset_dir(base: Path, fixture_root: Path) -> None:
    assets = base / "empty-assets"
    assets.mkdir(parents=True, exist_ok=True)
    work_dir = base / "empty-asset-output"
    code, _, stderr = _run(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            str(fixture_root / "scenario-a-product" / "reference.mp4"),
            "--assets",
            str(assets),
            "--work-dir",
            str(work_dir),
        ]
    )
    if code == 0:
        raise AssertionError("empty asset directory should fail")
    if "asset" not in stderr.lower():
        raise AssertionError("empty asset directory did not report asset failure")
    _assert_no_remix(work_dir)


def test_damaged_asset_dir(base: Path, fixture_root: Path) -> None:
    assets = base / "damaged-assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixture_root / "malformed" / "damaged.mp4", assets / "damaged.mp4")
    work_dir = base / "damaged-output"
    code, _, stderr = _run(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            str(fixture_root / "scenario-a-product" / "reference.mp4"),
            "--assets",
            str(assets),
            "--work-dir",
            str(work_dir),
        ]
    )
    if code == 0:
        raise AssertionError("damaged-only asset directory should fail")
    if "asset" not in stderr.lower():
        raise AssertionError("damaged-only asset directory did not report asset failure")
    _assert_no_remix(work_dir)


def test_chinese_path_with_spaces(base: Path, fixture_root: Path) -> None:
    source = fixture_root / "scenario-a-product"
    scenario = base / "中文 路径" / "产品 样例"
    shutil.copytree(source, scenario)
    work_dir = base / "中文 输出"
    code, _, stderr = _run(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            str(scenario / "reference.mp4"),
            "--assets",
            str(scenario / "assets"),
            "--script",
            str(scenario / "script.txt"),
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
        raise AssertionError(f"Chinese path smoke should pass: {stderr}")
    if not (work_dir / "remix.mp4").exists():
        raise AssertionError("Chinese path smoke did not create remix.mp4")
    if not (work_dir / "review.html").exists():
        raise AssertionError("Chinese path smoke did not create review.html")


def main() -> int:
    base = ROOT / "out" / f"p0-{os.getpid()}"
    _reset_dir(base)
    fixture_root = base / "fixtures"
    generate_fixtures(fixture_root)
    test_missing_reference(base, fixture_root)
    test_empty_asset_dir(base, fixture_root)
    test_damaged_asset_dir(base, fixture_root)
    test_chinese_path_with_spaces(base, fixture_root)
    print("p0 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
