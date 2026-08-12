import subprocess
import sys
import wave
import math
import shutil
import struct
from pathlib import Path

from jianji_flow.cli import main
from jianji_flow.media_probe import run_ffprobe
from jianji_flow.voiceover import probe_voiceover


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


def test_doctor_prints_environment_report(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "jianji_flow.cli.check_environment",
        lambda output_root=None: {"status": "pass", "checks": {"python": {"status": "pass", "message": "Python ok"}}},
    )
    monkeypatch.setattr(
        "jianji_flow.cli.format_environment_report",
        lambda report: "# Environment\n- python: OK - Python ok\n\nReady to run quick draft\n",
    )

    code = main(["doctor", "--work-dir", str(tmp_path)])
    output = capsys.readouterr()

    assert code == 0
    assert "Ready to run quick draft" in output.out


def test_doctor_returns_failure_when_environment_is_not_ready(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "jianji_flow.cli.check_environment",
        lambda output_root=None: {"status": "fail", "checks": {"local_tts": {"status": "fail", "message": "TTS missing"}}},
    )
    monkeypatch.setattr(
        "jianji_flow.cli.format_environment_report",
        lambda report: "# Environment\n- local_tts: FAIL - TTS missing\n\nNot ready\n",
    )

    code = main(["doctor", "--work-dir", str(tmp_path)])
    output = capsys.readouterr()

    assert code == 1
    assert "Not ready" in output.out


def test_doctor_is_environment_only_for_now(capsys):
    code = main(["doctor", "--assets", "assets"])
    output = capsys.readouterr()

    assert code == 2
    assert "unrecognized arguments" in output.err


def test_demo_runs_generated_fixture(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    work_dir = tmp_path / "demo"

    code = main(
        [
            "demo",
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
    assert (work_dir / "remix.mp4").exists()
    assert (work_dir / "review.html").exists()


def test_demo_reports_fixture_generation_failure_without_traceback(tmp_path, monkeypatch, capsys):
    def fake_generate_fixtures(output: Path) -> None:
        raise RuntimeError("fixture generation failed")

    monkeypatch.setattr("jianji_flow.cli.generate_fixtures", fake_generate_fixtures)

    code = main(["demo", "--work-dir", str(tmp_path / "demo")])
    output = capsys.readouterr()

    assert code == 1
    assert "jianji-flow failed" in output.err
    assert "Traceback" not in output.err
    assert (tmp_path / "demo" / "review.md").exists()


def test_quick_uses_default_product_script_when_script_is_missing(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    work_dir = tmp_path / "quick"

    code = main(
        [
            "quick",
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
    )

    assert code == 0
    assert (work_dir / "remix.mp4").exists()
    assert "家里乱" in (work_dir / "captions.srt").read_text(encoding="utf-8")


def test_quick_talking_head_requires_script(tmp_path, capsys):
    code = main(
        [
            "quick",
            "--mode",
            "talking-head",
            "--reference",
            str(tmp_path / "ref.mp4"),
            "--assets",
            str(tmp_path / "assets"),
            "--work-dir",
            str(tmp_path / "quick"),
        ]
    )
    output = capsys.readouterr()

    assert code == 2
    assert "script" in output.err.lower()


def test_quick_reports_missing_reference_without_traceback(tmp_path, capsys):
    assets = tmp_path / "assets"
    assets.mkdir()

    code = main(
        [
            "quick",
            "--reference",
            str(tmp_path / "missing.mp4"),
            "--assets",
            str(assets),
            "--work-dir",
            str(tmp_path / "quick"),
        ]
    )
    output = capsys.readouterr()

    assert code == 1
    assert "jianji-flow failed" in output.err
    assert "Traceback" not in output.err
    assert (tmp_path / "quick" / "review.md").exists()


def test_quick_stops_before_render_when_product_roles_are_missing(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    first_asset = next((fixture_root / "scenario-a-product" / "assets").glob("*.mp4"))
    shutil.copy(first_asset, incomplete / "01-hook.mp4")
    work_dir = tmp_path / "quick"

    code = main(
        [
            "quick",
            "--reference",
            str(fixture_root / "scenario-a-product" / "reference.mp4"),
            "--assets",
            str(incomplete),
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
    assert (work_dir / "diagnosis.md").exists()
    assert "缺少" in (work_dir / "diagnosis.md").read_text(encoding="utf-8")
    assert not (work_dir / "remix.mp4").exists()


def test_quick_material_failure_removes_stale_review_outputs(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    work_dir = tmp_path / "quick"
    success_args = [
        "quick",
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
    assert (work_dir / "review.md").exists()
    assert (work_dir / "recipe.json").exists()

    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    first_asset = next((fixture_root / "scenario-a-product" / "assets").glob("*.mp4"))
    shutil.copy(first_asset, incomplete / "01-hook.mp4")
    failed_args = success_args.copy()
    failed_args[failed_args.index("--assets") + 1] = str(incomplete)

    assert main(failed_args) == 1
    assert (work_dir / "diagnosis.md").exists()
    for name in ("review.md", "review.html", "manifest.json", "recipe.json", "matches.json", "captions.srt", "captions.ass"):
        assert not (work_dir / name).exists(), name


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


def test_run_shortens_voiceover_timeline_instead_of_padding_silent_tail(tmp_path, monkeypatch):
    def fake_create_voiceover(recipe: dict, output_path: Path, *, rate: int = 0) -> Path:
        duration_ms = int(recipe.get("duration_ms", 1000) or 1000)
        _write_test_wav(output_path, seconds=max(0.25, duration_ms / 1000 * 0.8))
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

    recipe = __import__("json").loads((work_dir / "recipe.json").read_text(encoding="utf-8"))
    voiceover_duration = probe_voiceover(work_dir / "voiceover.wav").duration_ms
    remix_duration = run_ffprobe(work_dir / "remix.mp4").duration_ms

    assert code == 0
    assert abs(recipe["duration_ms"] - voiceover_duration) <= 100
    assert abs(remix_duration - voiceover_duration) <= 250
    assert recipe["segments"][-1]["end_ms"] == recipe["duration_ms"]


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
