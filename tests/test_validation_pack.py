import json
import shutil
from pathlib import Path

from jianji_flow.cli import main
from jianji_flow.validation_pack import build_validation_pack


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fresh_dir(name: str) -> Path:
    path = PROJECT_ROOT / "out" / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_run_artifacts(run_dir: Path, *, status: str = "pass") -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "review.md").write_text(f"# Review\n\nStatus: {status}\n", encoding="utf-8")
    (run_dir / "review.html").write_text(f"<html>Status: {status}</html>\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text('{"assets":[{"sha256":"abc"}]}\n', encoding="utf-8")
    (run_dir / "remix.mp4").write_bytes(b"video placeholder")
    (run_dir / "contact-sheet.png").write_bytes(b"image placeholder")


def test_build_validation_pack_uses_pending_human_judgment_for_real_material():
    run_dir = _fresh_dir("pytest-validation-pack-real-run")
    _write_run_artifacts(run_dir)

    pack = build_validation_pack(
        run_dir,
        name="home-cleaning-real-01",
        kind="real",
        independent=True,
        opaque_filenames=True,
    )

    entry = pack["release_gate_entry"]
    assert pack["observed_review_status"] == "pass"
    assert pack["missing_artifacts"] == []
    assert entry["name"] == "home-cleaning-real-01"
    assert entry["independent"] is True
    assert entry["opaque_filenames"] is True
    assert entry["human_judgment"] == "pending"
    assert entry["review"].endswith("review.md")
    assert entry["manifest"].endswith("manifest.json")
    assert "manual pass" in pack["human_judgment_markdown"]


def test_build_validation_pack_dirty_material_uses_expected_absent_remix_path():
    run_dir = _fresh_dir("pytest-validation-pack-dirty-run")
    _write_run_artifacts(run_dir, status="fail")
    (run_dir / "remix.mp4").unlink()

    pack = build_validation_pack(run_dir, name="dirty-platform-ui-01", kind="dirty")

    entry = pack["release_gate_entry"]
    assert pack["observed_review_status"] == "fail"
    assert entry["human_judgment"] == "pending"
    assert entry["remix"].endswith("remix.mp4")
    assert "contact_sheet" not in entry
    assert "remix.mp4 is absent" in pack["human_judgment_markdown"]


def test_evidence_pack_cli_writes_pack_entry_and_judgment_template():
    run_dir = _fresh_dir("pytest-validation-pack-cli-run")
    output_dir = _fresh_dir("pytest-validation-pack-cli-output")
    _write_run_artifacts(run_dir)

    code = main(
        [
            "evidence-pack",
            "--run-dir",
            str(run_dir),
            "--name",
            "home-cleaning-real-01",
            "--kind",
            "real",
            "--output-dir",
            str(output_dir),
            "--independent",
            "--opaque-filenames",
        ]
    )

    pack = json.loads((output_dir / "validation-pack.json").read_text(encoding="utf-8"))
    entry = json.loads((output_dir / "release-evidence.entry.json").read_text(encoding="utf-8"))
    judgment = (output_dir / "human-judgment.md").read_text(encoding="utf-8")

    assert code == 0
    assert pack["release_gate_entry"] == entry
    assert entry["human_judgment"] == "pending"
    assert "home-cleaning-real-01" in judgment
    assert "visible remix" in judgment
