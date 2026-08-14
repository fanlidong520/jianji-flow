import json
import subprocess
import sys
import wave
import math
import shutil
import struct
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from jianji_flow.cli import main
from jianji_flow.contracts import validate_fixes
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


def _contact_sheet_tile(path: Path, index: int, *, tile_width: int = 220, padding: int = 8) -> Image.Image:
    image = Image.open(path).convert("RGB")
    left = padding + index * (tile_width + padding)
    return image.crop((left, padding, left + tile_width, image.height - padding))


def _mean_image_difference(left: Image.Image, right: Image.Image) -> float:
    diff = ImageChops.difference(left, right)
    return sum(ImageStat.Stat(diff).mean) / 3


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


def test_quick_writes_material_diagnosis_even_when_assets_are_ready(tmp_path, monkeypatch):
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

    diagnosis = work_dir / "diagnosis.md"
    assert code == 0
    assert diagnosis.exists()
    text = diagnosis.read_text(encoding="utf-8")
    assert "Filename and duration screening only" in text
    assert "CANDIDATE" in text
    assert "READY" not in text
    assert "not visual proof" in text
    assert "Can run quick draft; inspect contact-sheet before publishing" in text


def test_quick_appends_source_preflight_warning_to_material_diagnosis(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)

    def fake_source_preflight(recipe, matches, diagnostics_dir, **kwargs):
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        (diagnostics_dir / "seg-001-01.png").write_bytes(b"diagnostic frame")
        return {
            "status": "warning",
            "failures": [],
            "warnings": ["seg-001 source frame 1: possible platform UI before rendering"],
            "metrics": {},
            "diagnostics_dir": diagnostics_dir.as_posix(),
        }

    monkeypatch.setattr("jianji_flow.cli.diagnose_source_matches", fake_source_preflight)
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

    diagnosis = (work_dir / "diagnosis.md").read_text(encoding="utf-8")
    assert code == 0
    assert "## Source preflight" in diagnosis
    assert "WARNING - seg-001 source frame 1" in diagnosis
    assert "source-diagnostics" in diagnosis


def test_quick_appends_source_preflight_failure_to_material_diagnosis(tmp_path, monkeypatch):
    def forbidden_create_voiceover(*args, **kwargs):
        raise AssertionError("voiceover should not run after source preflight failure")

    def fake_source_preflight(recipe, matches, diagnostics_dir, **kwargs):
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        (diagnostics_dir / "seg-001-01.png").write_bytes(b"diagnostic frame")
        return {
            "status": "fail",
            "failures": ["seg-001 source frame 1: severe platform UI before rendering"],
            "warnings": [],
            "metrics": {},
            "diagnostics_dir": diagnostics_dir.as_posix(),
        }

    monkeypatch.setattr("jianji_flow.cli.create_voiceover", forbidden_create_voiceover)
    monkeypatch.setattr("jianji_flow.cli.diagnose_source_matches", fake_source_preflight)
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

    diagnosis = (work_dir / "diagnosis.md").read_text(encoding="utf-8")
    assert code == 1
    assert "## Source preflight" in diagnosis
    assert "FAIL - seg-001 source frame 1" in diagnosis
    assert "source-diagnostics" in diagnosis
    assert not (work_dir / "remix.mp4").exists()


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
        "reference-comparison.png",
        "candidate-review.html",
        "fixes.template.json",
        "review.md",
        "review.html",
    ):
        assert (work_dir / name).exists(), name
    assert (work_dir / "candidate-frames").is_dir()
    assert run_ffprobe(work_dir / "remix.mp4").has_audio is True
    review_html = (work_dir / "review.html").read_text(encoding="utf-8")
    review_md = (work_dir / "review.md").read_text(encoding="utf-8")
    candidate_html = (work_dir / "candidate-review.html").read_text(encoding="utf-8")
    fixes_template = json.loads((work_dir / "fixes.template.json").read_text(encoding="utf-8"))
    validate_fixes(fixes_template)
    assert "<video" in review_html
    assert "voiceover.wav" in review_html
    assert "reference-comparison.png" in review_html
    assert "Reference vs Remix" in review_html
    assert "candidate-review.html" in review_md
    assert "candidate-review.html" in review_html
    assert "Current segment" in candidate_html
    assert "Candidate" in candidate_html
    assert "role mismatch" in candidate_html
    assert list((work_dir / "candidate-frames").glob("*.png"))
    assert "fixes.template.json" in review_md
    assert "fixes.template.json" in review_html
    assert fixes_template["segments"]


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
    for name in (
        "voiceover.wav",
        "captions.ass",
        "contact-sheet.png",
        "shot-contact-sheet.png",
        "reference-comparison.png",
        "shot-plan.json",
        "review.html",
    ):
        (work_dir / name).write_bytes(b"stale")

    empty_assets = tmp_path / "empty-assets"
    empty_assets.mkdir()
    failed_args = success_args.copy()
    failed_args[failed_args.index("--assets") + 1] = str(empty_assets)

    assert main(failed_args) == 1
    for name in (
        "remix.mp4",
        "voiceover.wav",
        "captions.ass",
        "contact-sheet.png",
        "shot-contact-sheet.png",
        "reference-comparison.png",
        "shot-plan.json",
        "review.html",
    ):
        assert not (work_dir / name).exists(), name


def test_failed_review_keeps_diagnostic_contact_sheet_without_success_artifacts(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)

    def fake_build_review(*args, **kwargs):
        return {
            "status": "fail",
            "failures": ["forced artifact failure"],
            "warnings": [],
            "missing_segments": [],
            "low_confidence_segments": [],
            "outputs": {
                "remix": (work_dir / "remix.mp4").as_posix(),
                "voiceover": (work_dir / "voiceover.wav").as_posix(),
                "captions_ass": (work_dir / "captions.ass").as_posix(),
                "contact_sheet": (work_dir / "contact-sheet.png").as_posix(),
                "review_html": (work_dir / "review.html").as_posix(),
            },
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
    review = (work_dir / "review.md").read_text(encoding="utf-8")
    assert "forced artifact failure" in review
    assert "contact_sheet" in review
    assert "candidate_review" not in review
    assert "candidate_frames" not in review
    assert (work_dir / "contact-sheet.png").exists()
    assert (work_dir / "contact-sheet.png").stat().st_size > 0
    for name in ("remix.mp4", "voiceover.wav", "captions.ass", "candidate-review.html", "review.html"):
        assert not (work_dir / name).exists(), name
    assert not (work_dir / "candidate-frames").exists()


def test_source_preflight_failure_stops_before_voiceover_and_render(tmp_path, monkeypatch):
    def forbidden_create_voiceover(*args, **kwargs):
        raise AssertionError("voiceover should not run after source preflight failure")

    def fake_source_preflight(recipe, matches, diagnostics_dir, **kwargs):
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        (diagnostics_dir / "seg-001-01.png").write_bytes(b"diagnostic frame")
        return {
            "status": "fail",
            "failures": ["seg-001 source frame 1: severe platform UI before rendering"],
            "warnings": [],
            "metrics": {},
            "diagnostics_dir": diagnostics_dir.as_posix(),
        }

    monkeypatch.setattr("jianji_flow.cli.create_voiceover", forbidden_create_voiceover)
    monkeypatch.setattr("jianji_flow.cli.diagnose_source_matches", fake_source_preflight)
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

    review = (work_dir / "review.md").read_text(encoding="utf-8")
    assert code == 1
    assert "source frame 1" in review
    assert "source_diagnostics" in review
    assert (work_dir / "source-diagnostics" / "seg-001-01.png").exists()
    for name in ("remix.mp4", "voiceover.wav", "captions.ass", "contact-sheet.png", "review.html"):
        assert not (work_dir / name).exists(), name


def test_source_preflight_warning_is_reported_in_final_review(tmp_path, monkeypatch, capsys):
    _patch_voiceover(monkeypatch)

    def fake_source_preflight(recipe, matches, diagnostics_dir, **kwargs):
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        (diagnostics_dir / "seg-001-01.png").write_bytes(b"diagnostic frame")
        return {
            "status": "warning",
            "failures": [],
            "warnings": ["seg-001 source frame 1: possible platform UI before rendering"],
            "metrics": {},
            "diagnostics_dir": diagnostics_dir.as_posix(),
        }

    monkeypatch.setattr("jianji_flow.cli.diagnose_source_matches", fake_source_preflight)
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
    output = capsys.readouterr()

    review = (work_dir / "review.md").read_text(encoding="utf-8")
    assert code == 0
    assert "review required" in output.out
    assert "completed" not in output.out
    assert "Status: warning" in review
    assert "source frame 1" in review
    assert "source_diagnostics" in review
    assert (work_dir / "source-diagnostics" / "seg-001-01.png").exists()
    assert (work_dir / "remix.mp4").exists()


def test_source_preflight_clean_evidence_is_written_to_matches(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)

    def fake_source_preflight(recipe, matches, diagnostics_dir, **kwargs):
        return {
            "status": "pass",
            "failures": [],
            "warnings": [],
            "metrics": {},
            "diagnostics_dir": diagnostics_dir.as_posix(),
            "clean_segment_ids": ["seg-001", "seg-002"],
        }

    monkeypatch.setattr("jianji_flow.cli.diagnose_source_matches", fake_source_preflight)
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

    matches = json.loads((work_dir / "matches.json").read_text(encoding="utf-8"))
    evidence_by_segment = {item["segment_id"]: item["evidence"] for item in matches["matches"]}
    assert code == 0
    assert "source-preflight:clean" in evidence_by_segment["seg-001"]
    assert "source-preflight:clean" in evidence_by_segment["seg-002"]


def test_run_applies_fixes_file_to_one_segment(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    work_dir = tmp_path / "work"
    replacement = scenario / "assets" / "05-cta-packshot-buy.mp4"
    fixes_path = tmp_path / "fixes.json"
    fixes_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "segments": {
                    "seg-003": {
                        "asset_path": str(replacement),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(
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
            "--fixes",
            str(fixes_path),
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

    matches = json.loads((work_dir / "matches.json").read_text(encoding="utf-8"))
    by_segment = {item["segment_id"]: item for item in matches["matches"]}
    assert code == 0
    assert by_segment["seg-003"]["source_path"].replace("\\", "/").endswith("05-cta-packshot-buy.mp4")
    assert "override:seg-003" in by_segment["seg-003"]["evidence"]
    assert by_segment["seg-003"]["scores"]["override"] == 1.0


def test_run_applies_clean_recommendation_from_fixes_template(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    work_dir = tmp_path / "work"
    replacement = scenario / "assets" / "05-cta-packshot-buy.mp4"
    fixes_path = tmp_path / "fixes.template.json"
    fixes_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "segments": {
                    "seg-003": {
                        "asset_path": "",
                        "recommended_asset_path": str(replacement),
                        "recommendation_status": "recommended",
                        "recommendation_warnings": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(
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
            "--fixes",
            str(fixes_path),
            "--apply-recommendation",
            "seg-003",
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

    matches = json.loads((work_dir / "matches.json").read_text(encoding="utf-8"))
    by_segment = {item["segment_id"]: item for item in matches["matches"]}
    assert code == 0
    assert by_segment["seg-003"]["source_path"].replace("\\", "/").endswith("05-cta-packshot-buy.mp4")
    assert "override:seg-003" in by_segment["seg-003"]["evidence"]


def test_run_applies_recommended_source_window_from_fixes_template(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    base_work_dir = tmp_path / "base"
    fixed_work_dir = tmp_path / "fixed"
    feature = scenario / "assets" / "03-feature-product-detail.mp4"
    base_args = [
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
        str(base_work_dir),
        "--target-width",
        "320",
        "--target-height",
        "180",
        "--target-fps",
        "12",
    ]

    assert main(base_args) == 0
    fixes_path = tmp_path / "fixes.template.json"
    fixes_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "segments": {
                    "seg-003": {
                        "asset_path": "",
                        "recommended_asset_path": str(feature),
                        "recommended_source_start_ms": 900,
                        "recommendation_status": "recommended",
                        "recommendation_warnings": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    fixed_args = [
        "run",
        "--mode",
        "product",
        "--reference",
        str(scenario / "reference.mp4"),
        "--assets",
        str(scenario / "assets"),
        "--script",
        str(scenario / "script.txt"),
        "--fixes",
        str(fixes_path),
        "--apply-recommendation",
        "seg-003",
        "--work-dir",
        str(fixed_work_dir),
        "--target-width",
        "320",
        "--target-height",
        "180",
        "--target-fps",
        "12",
    ]

    assert main(fixed_args) == 0
    matches = json.loads((fixed_work_dir / "matches.json").read_text(encoding="utf-8"))
    by_segment = {item["segment_id"]: item for item in matches["matches"]}

    assert by_segment["seg-003"]["source_path"].replace("\\", "/").endswith("03-feature-product-detail.mp4")
    assert by_segment["seg-003"]["source_start_ms"] == 900
    assert by_segment["seg-003"]["source_end_ms"] > by_segment["seg-003"]["source_start_ms"]
    assert "source-window:" in " ".join(by_segment["seg-003"]["evidence"])
    assert "override:seg-003" in by_segment["seg-003"]["evidence"]
    review_markdown = (fixed_work_dir / "review.md").read_text(encoding="utf-8")
    review_html = (fixed_work_dir / "review.html").read_text(encoding="utf-8")
    assert "candidate-review.html" in review_markdown
    assert "## Change report" in review_markdown
    assert "seg-003" in review_markdown
    assert "03-feature-product-detail.mp4 @ " in review_markdown
    assert "Picture change" in review_markdown
    assert "Picture change only means sampled frames differ" in review_markdown
    assert "source-window changed" in review_markdown or "override:seg-003" in review_markdown
    assert "Change report" in review_html
    assert "seg-003" in review_html
    assert "03-feature-product-detail.mp4 @ " in review_html
    assert "Picture change only means sampled frames differ" in review_html
    assert "seg-003-before.png" in review_html
    assert "seg-003-after.png" in review_html
    assert "change_diagnostics" in review_markdown
    assert (fixed_work_dir / "change-diagnostics").exists()
    assert (fixed_work_dir / "change-diagnostics" / "seg-003-before.png").exists()
    assert (fixed_work_dir / "change-diagnostics" / "seg-003-after.png").exists()


def test_run_rejects_warning_recommendation_without_traceback(tmp_path, monkeypatch, capsys):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    work_dir = tmp_path / "work"
    replacement = scenario / "assets" / "05-cta-packshot-buy.mp4"
    fixes_path = tmp_path / "fixes.template.json"
    fixes_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "segments": {
                    "seg-003": {
                        "asset_path": "",
                        "recommended_asset_path": str(replacement),
                        "recommendation_status": "best_available_with_warnings",
                        "recommendation_warnings": ["would repeat adjacent segment"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(
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
            "--fixes",
            str(fixes_path),
            "--apply-recommendation",
            "seg-003",
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
    output = capsys.readouterr()

    assert code == 1
    assert "best_available_with_warnings" in output.err
    assert "Traceback" not in output.err
    assert "would repeat adjacent segment" in (work_dir / "review.md").read_text(encoding="utf-8")
    assert not (work_dir / "remix.mp4").exists()


def test_fixes_file_visibly_changes_replaced_segment(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    base_work_dir = tmp_path / "base"
    fixed_work_dir = tmp_path / "fixed"
    base_args = [
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
        str(base_work_dir),
        "--target-width",
        "320",
        "--target-height",
        "180",
        "--target-fps",
        "12",
    ]

    assert main(base_args) == 0
    fixes_path = tmp_path / "fixes.json"
    fixes_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "segments": {
                    "seg-003": {
                        "asset_path": str(scenario / "assets" / "05-cta-packshot-buy.mp4"),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    fixed_args = [
        "run",
        "--mode",
        "product",
        "--reference",
        str(scenario / "reference.mp4"),
        "--assets",
        str(scenario / "assets"),
        "--script",
        str(scenario / "script.txt"),
        "--fixes",
        str(fixes_path),
        "--work-dir",
        str(fixed_work_dir),
        "--target-width",
        "320",
        "--target-height",
        "180",
        "--target-fps",
        "12",
    ]

    assert main(fixed_args) == 0
    base_tile = _contact_sheet_tile(base_work_dir / "contact-sheet.png", 2)
    fixed_tile = _contact_sheet_tile(fixed_work_dir / "contact-sheet.png", 2)

    assert _mean_image_difference(base_tile, fixed_tile) > 15


def test_run_reports_invalid_fixes_file_without_traceback(tmp_path, monkeypatch, capsys):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    work_dir = tmp_path / "work"
    fixes_path = tmp_path / "fixes.json"
    fixes_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "segments": {"seg-003": {"asset_path": str(scenario / "assets" / "missing.mp4")}},
            }
        ),
        encoding="utf-8",
    )

    code = main(
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
            "--fixes",
            str(fixes_path),
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
    output = capsys.readouterr()

    assert code == 1
    assert "jianji-flow failed" in output.err
    assert "Traceback" not in output.err
    review = (work_dir / "review.md").read_text(encoding="utf-8")
    assert "asset_path not found" in review
    assert "missing.mp4" in review
    assert not (work_dir / "remix.mp4").exists()


def test_run_reports_fixes_schema_errors_concisely(tmp_path, monkeypatch, capsys):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    work_dir = tmp_path / "work"
    fixes_path = tmp_path / "fixes.json"
    fixes_path.write_text(json.dumps({"segments": {"seg-003": {"asset_path": "assets/demo.mp4"}}}), encoding="utf-8")

    code = main(
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
            "--fixes",
            str(fixes_path),
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
    output = capsys.readouterr()
    review = (work_dir / "review.md").read_text(encoding="utf-8")

    assert code == 1
    assert "fixes file schema error" in output.err
    assert "fixes file schema error" in review
    assert "required property" in review
    assert "$schema" not in review
    assert "json-schema.org" not in review


def test_run_accepts_utf8_sig_fixes_file_from_windows_editors(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    work_dir = tmp_path / "work"
    fixes_path = tmp_path / "fixes.json"
    fixes_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "segments": {
                    "seg-003": {
                        "asset_path": str(scenario / "assets" / "05-cta-packshot-buy.mp4"),
                    }
                },
            }
        ),
        encoding="utf-8-sig",
    )

    code = main(
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
            "--fixes",
            str(fixes_path),
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
    matches = json.loads((work_dir / "matches.json").read_text(encoding="utf-8"))
    assert "override:seg-003" in {item["segment_id"]: item["evidence"] for item in matches["matches"]}["seg-003"]


def test_run_passes_visual_window_scorer_to_matcher(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    seen = {"window_scorer": False}

    import jianji_flow.cli as cli_module

    original_match_segments = cli_module.match_segments

    def spy_match_segments(segments, records, threshold=0.6, *, window_scorer=None):
        seen["window_scorer"] = window_scorer is not None
        return original_match_segments(segments, records, threshold=threshold, window_scorer=window_scorer)

    monkeypatch.setattr("jianji_flow.cli.match_segments", spy_match_segments)
    monkeypatch.setattr("jianji_flow.cli.score_source_window", lambda *args, **kwargs: 0.5)
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
    assert seen["window_scorer"] is True


def test_run_reports_visual_similarity_diagnostics_for_duplicate_recommendation(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    monkeypatch.setattr("jianji_flow.cli.score_source_window", lambda asset, start_ms, end_ms, diagnostics_dir: -float(start_ms))
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    original = scenario / "assets" / "03-feature-product-detail.mp4"
    duplicate = scenario / "assets" / "03b-feature-product-detail-copy.mp4"
    shutil.copy(original, duplicate)
    work_dir = tmp_path / "work"

    code = main(
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

    fixes_template = json.loads((work_dir / "fixes.template.json").read_text(encoding="utf-8"))
    segment = fixes_template["segments"]["seg-003"]
    review = (work_dir / "review.md").read_text(encoding="utf-8")

    assert code == 0
    assert segment["recommended_asset_path"].replace("\\", "/").endswith("03b-feature-product-detail-copy.mp4")
    assert segment["recommendation_status"] == "best_available_with_warnings"
    assert segment["recommendation_warnings"] == ["visually similar to current segment"]
    assert "visual_similarity_diagnostics" in review
    assert len(list((work_dir / "visual-similarity-diagnostics").glob("*.png"))) >= 6


def test_run_removes_stale_visual_similarity_diagnostics_on_rerun(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    monkeypatch.setattr("jianji_flow.cli.score_source_window", lambda asset, start_ms, end_ms, diagnostics_dir: -float(start_ms))
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    original = scenario / "assets" / "03-feature-product-detail.mp4"
    duplicate = scenario / "assets" / "03b-feature-product-detail-copy.mp4"
    shutil.copy(original, duplicate)
    work_dir = tmp_path / "work"
    args = [
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

    assert main(args) == 0
    assert (work_dir / "visual-similarity-diagnostics").exists()

    duplicate.unlink()
    assert main(args) == 0

    review = (work_dir / "review.md").read_text(encoding="utf-8")
    diagnostic_dir = work_dir / "visual-similarity-diagnostics"
    diagnostic_names = [path.name for path in diagnostic_dir.glob("*.png")]
    assert "03b-feature-product-detail-copy" not in "\n".join(diagnostic_names)
    assert diagnostic_names


def test_run_removes_stale_candidate_frames_on_rerun(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    scenario = fixture_root / "scenario-a-product"
    work_dir = tmp_path / "work"
    args = [
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

    assert main(args) == 0
    stale_frame = work_dir / "candidate-frames" / "stale.png"
    stale_frame.write_bytes(b"stale")

    assert main(args) == 0

    assert (work_dir / "candidate-review.html").exists()
    assert not stale_frame.exists()


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
