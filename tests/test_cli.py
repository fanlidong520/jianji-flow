import subprocess
import sys
from pathlib import Path

from jianji_flow.cli import main
from jianji_flow.media_probe import run_ffprobe


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = PROJECT_ROOT / "scripts" / "generate_fixtures.py"


def test_cli_version(capsys):
    code = main(["--version"])
    output = capsys.readouterr()
    assert code == 0
    assert "jianji-flow 0.1.0" in output.out


def test_cli_help_no_args(capsys):
    code = main([])
    output = capsys.readouterr()
    assert code == 0
    assert "run" in output.out


def test_cli_help_when_argv_none(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["jianji-flow"])
    code = main(None)
    output = capsys.readouterr()
    assert code == 0
    assert "run" in output.out


def test_run_reports_missing_paths(tmp_path, capsys):
    code = main(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            str(tmp_path / "ref.mp4"),
            "--assets",
            str(tmp_path / "assets"),
            "--work-dir",
            str(tmp_path / "work"),
        ]
    )
    output = capsys.readouterr()
    assert code == 1
    assert "missing" in output.err.lower() or "not found" in output.err.lower()


def test_run_requires_reference(capsys):
    code = main(["run", "--mode", "product", "--assets", "assets", "--work-dir", "work"])
    output = capsys.readouterr()
    assert code == 2
    assert "reference" in output.err.lower()


def test_cli_rejects_invalid_mode(capsys):
    code = main(["run", "--mode", "bad", "--reference", "ref.mp4", "--assets", "assets", "--work-dir", "work"])
    output = capsys.readouterr()
    assert code == 2
    assert "invalid choice" in output.err.lower()


def test_run_product_fixture_creates_outputs(tmp_path):
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    work_dir = tmp_path / "work"

    code = main(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            str(fixture_root / "scenario-a-product" / "reference.mp4"),
            "--assets",
            str(fixture_root / "scenario-a-product" / "assets"),
            "--script",
            str(fixture_root / "scenario-a-product" / "script.txt"),
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

    assert code == 0
    for name in ("manifest.json", "recipe.json", "matches.json", "captions.srt", "remix.mp4", "review.md"):
        assert (work_dir / name).exists(), name
    assert "Status:" in (work_dir / "review.md").read_text(encoding="utf-8")
    assert run_ffprobe(work_dir / "remix.mp4").duration_ms > 0


def test_failed_rerun_removes_stale_remix(tmp_path):
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    work_dir = tmp_path / "work"
    success_args = [
        "run",
        "--mode",
        "product",
        "--reference",
        str(fixture_root / "scenario-a-product" / "reference.mp4"),
        "--assets",
        str(fixture_root / "scenario-a-product" / "assets"),
        "--work-dir",
        str(work_dir),
        "--target-width",
        "320",
        "--target-height",
        "180",
        "--target-fps",
        "12",
    ]
    assert main(success_args) == 0
    assert (work_dir / "remix.mp4").exists()

    empty_assets = tmp_path / "empty-assets"
    empty_assets.mkdir()
    failed_args = success_args.copy()
    failed_args[failed_args.index("--assets") + 1] = str(empty_assets)

    assert main(failed_args) == 1
    assert not (work_dir / "remix.mp4").exists()
