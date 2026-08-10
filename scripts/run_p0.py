from __future__ import annotations

import shutil
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
    if (work_dir / "remix.mp4").exists():
        raise AssertionError(f"blocking failure produced remix.mp4: {work_dir}")


def test_missing_reference(base: Path) -> None:
    work_dir = base / "missing-reference"
    code, _, stderr = _run(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            str(base / "missing.mp4"),
            "--assets",
            str(ROOT / "fixtures" / "scenario-a-product" / "assets"),
            "--work-dir",
            str(work_dir),
        ]
    )
    if code == 0:
        raise AssertionError("missing reference should fail")
    if "failed" not in stderr.lower():
        raise AssertionError("missing reference did not report failure")
    _assert_no_remix(work_dir)


def test_empty_asset_dir(base: Path) -> None:
    assets = base / "empty-assets"
    assets.mkdir(parents=True, exist_ok=True)
    work_dir = base / "empty-asset-output"
    code, _, stderr = _run(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            str(ROOT / "fixtures" / "scenario-a-product" / "reference.mp4"),
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


def test_damaged_asset_dir(base: Path) -> None:
    assets = base / "damaged-assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "fixtures" / "malformed" / "damaged.mp4", assets / "damaged.mp4")
    work_dir = base / "damaged-output"
    code, _, stderr = _run(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            str(ROOT / "fixtures" / "scenario-a-product" / "reference.mp4"),
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


def test_chinese_path_with_spaces(base: Path) -> None:
    source = ROOT / "fixtures" / "scenario-a-product"
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


def main() -> int:
    generate_fixtures(ROOT / "fixtures")
    base = ROOT / "out" / "p0"
    _reset_dir(base)
    test_missing_reference(base)
    test_empty_asset_dir(base)
    test_damaged_asset_dir(base)
    test_chinese_path_with_spaces(base)
    print("p0 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
