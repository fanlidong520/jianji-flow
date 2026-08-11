import subprocess
import sys
import wave
import math
import struct
from pathlib import Path

from jianji_flow.cli import main
from jianji_flow.media_probe import run_ffprobe


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = PROJECT_ROOT / "scripts" / "generate_fixtures.py"


def _write_test_wav(path: Path, *, seconds: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    samples = int(sample_rate * seconds)
    frames = bytearray()
    for index in range(samples):
        value = int(math.sin(index / sample_rate * 440 * math.tau) * 8000)
        frames.extend(struct.pack("<h", value))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))


def _patch_voiceover(monkeypatch):
    def fake_create_voiceover(recipe: dict, output_path: Path, *, rate: int = 0) -> Path:
        duration_ms = int(recipe.get("duration_ms", 1000) or 1000)
        _write_test_wav(output_path, seconds=max(0.25, duration_ms / 1000 * 0.8))
        return output_path

    monkeypatch.setattr("jianji_flow.cli.create_voiceover", fake_create_voiceover, raising=False)


def test_cli_version(capsys):
    code = main(["--version"])
    output = capsys.readouterr()
    assert code == 0
    assert "jianji-flow 0.2.0" in output.out


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


def test_run_product_fixture_creates_outputs(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
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


def test_run_product_fixture_creates_v0_2_experience_outputs(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
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
        assert (work_dir / name).exists(), name
    assert run_ffprobe(work_dir / "remix.mp4").has_audio is True
    review_html = (work_dir / "review.html").read_text(encoding="utf-8")
    assert "<video" in review_html
    assert "voiceover.wav" in review_html


def test_failed_rerun_removes_stale_remix(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
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
    for name in ("voiceover.wav", "captions.ass", "contact-sheet.png", "review.html"):
        (work_dir / name).write_bytes(b"stale")

    empty_assets = tmp_path / "empty-assets"
    empty_assets.mkdir()
    failed_args = success_args.copy()
    failed_args[failed_args.index("--assets") + 1] = str(empty_assets)

    assert main(failed_args) == 1
    for name in ("remix.mp4", "voiceover.wav", "captions.ass", "contact-sheet.png", "review.html"):
        assert not (work_dir / name).exists(), name


def test_failed_review_removes_generated_success_artifacts(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)

    def fake_build_review(*args, **kwargs):
        return {
            "status": "fail",
            "failures": ["forced artifact failure"],
            "warnings": [],
            "missing_segments": [],
            "low_confidence_segments": [],
            "outputs": {},
        }

    monkeypatch.setattr("jianji_flow.cli.build_review", fake_build_review)
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

    assert code == 1
    assert "forced artifact failure" in (work_dir / "review.md").read_text(encoding="utf-8")
    for name in ("remix.mp4", "voiceover.wav", "captions.ass", "contact-sheet.png", "review.html"):
        assert not (work_dir / name).exists(), name


def test_semantic_failure_removes_generated_success_artifacts(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    monkeypatch.setattr("jianji_flow.cli.validate_semantics", lambda *args, **kwargs: ["forced semantic failure"])
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

    assert code == 1
    assert "forced semantic failure" in (work_dir / "review.md").read_text(encoding="utf-8")
    for name in ("remix.mp4", "voiceover.wav", "captions.ass", "contact-sheet.png", "review.html"):
        assert not (work_dir / name).exists(), name


def test_too_short_voiceover_removes_generated_success_artifacts(tmp_path, monkeypatch):
    def fake_create_voiceover(recipe: dict, output_path: Path, *, rate: int = 0) -> Path:
        _write_test_wav(output_path, seconds=0.1)
        return output_path

    monkeypatch.setattr("jianji_flow.cli.create_voiceover", fake_create_voiceover)
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

    assert code == 1
    assert "too short" in (work_dir / "review.md").read_text(encoding="utf-8")
    for name in ("remix.mp4", "voiceover.wav", "captions.ass", "contact-sheet.png", "review.html"):
        assert not (work_dir / name).exists(), name
