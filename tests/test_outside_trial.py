import json
import shutil
from pathlib import Path

import pytest

from jianji_flow.cli import main
from jianji_flow.outside_trial import build_outside_trial, build_outside_trial_result


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fresh_dir(name: str) -> Path:
    path = PROJECT_ROOT / "out" / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_build_outside_trial_defaults_to_unverified_release_gate_entry():
    trial = build_outside_trial("tester-01")

    entry = trial["release_gate_entry"]
    assert trial["release_gate_list"] == "outside_users"
    assert entry["id"] == "tester-01"
    assert entry["readme_quickstart"] is False
    assert entry["completed_in_minutes"] is None
    assert entry["visible_remix"] is None
    assert entry["review_status"] == ""
    assert "Did you reach a playable MP4" in trial["trial_markdown"]
    assert "Do not turn this into release evidence" in trial["trial_markdown"]


def test_build_outside_trial_rejects_blank_user_id():
    with pytest.raises(ValueError, match="stable tester id"):
        build_outside_trial(" ")


def test_outside_trial_cli_writes_template_files():
    output_dir = _fresh_dir("pytest-outside-trial-output")

    code = main(["outside-trial", "--id", "tester-01", "--output-dir", str(output_dir)])

    trial = json.loads((output_dir / "outside-trial.json").read_text(encoding="utf-8"))
    entry = json.loads((output_dir / "outside-user.entry.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "outside-user-trial.md").read_text(encoding="utf-8")
    assert code == 0
    assert trial["release_gate_entry"] == entry
    assert entry["readme_quickstart"] is False
    assert entry["visible_remix"] is None
    assert "tester-01" in markdown
    assert "exact command used" in markdown


def _write_demo_artifacts(demo_dir: Path, *, status: str = "warning") -> None:
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / "review.md").write_text(f"# jianji-flow Review\n\nStatus: {status}\n", encoding="utf-8")
    (demo_dir / "review.html").write_text("<html>review</html>", encoding="utf-8")
    (demo_dir / "remix.mp4").write_bytes(b"mp4")
    (demo_dir / "contact-sheet.png").write_bytes(b"png")


def test_build_outside_trial_result_records_explicit_tester_judgment():
    demo_dir = _fresh_dir("pytest-outside-trial-result-demo")
    _write_demo_artifacts(demo_dir, status="warning")

    result = build_outside_trial_result(
        "tester-01",
        demo_dir,
        completed_in_minutes=8,
        visible_remix=True,
        readme_quickstart=True,
        notes="Contact sheet made the changed shots obvious.",
    )

    entry = result["release_gate_entry"]
    assert entry["id"] == "tester-01"
    assert entry["readme_quickstart"] is True
    assert entry["completed_in_minutes"] == 8
    assert entry["visible_remix"] is True
    assert entry["review_status"] == "warning"
    assert result["artifact_check"]["status"] == "pass"
    assert "explicit tester judgment" in result["result_markdown"]


def test_build_outside_trial_result_rejects_missing_demo_artifacts():
    demo_dir = _fresh_dir("pytest-outside-trial-result-missing")
    (demo_dir / "review.md").write_text("Status: warning\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing trial artifact"):
        build_outside_trial_result(
            "tester-01",
            demo_dir,
            completed_in_minutes=8,
            visible_remix=True,
            readme_quickstart=True,
        )


def test_outside_trial_result_cli_writes_entry_and_result_files():
    demo_dir = _fresh_dir("pytest-outside-trial-result-cli-demo")
    output_dir = _fresh_dir("pytest-outside-trial-result-cli-output")
    _write_demo_artifacts(demo_dir, status="warning")

    code = main(
        [
            "outside-trial-result",
            "--id",
            "tester-01",
            "--demo-dir",
            str(demo_dir),
            "--completed-in-minutes",
            "8",
            "--visible-remix",
            "yes",
            "--readme-quickstart",
            "--output-dir",
            str(output_dir),
        ]
    )

    result = json.loads((output_dir / "outside-trial-result.json").read_text(encoding="utf-8"))
    entry = json.loads((output_dir / "outside-user.entry.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "outside-trial-result.md").read_text(encoding="utf-8")
    assert code == 0
    assert result["release_gate_entry"] == entry
    assert entry["readme_quickstart"] is True
    assert entry["visible_remix"] is True
    assert entry["review_status"] == "warning"
    assert "tester-01" in markdown


def test_outside_trial_result_cli_rejects_missing_artifacts_without_entry():
    demo_dir = _fresh_dir("pytest-outside-trial-result-cli-missing-demo")
    output_dir = _fresh_dir("pytest-outside-trial-result-cli-missing-output")
    (demo_dir / "review.md").write_text("Status: warning\n", encoding="utf-8")

    code = main(
        [
            "outside-trial-result",
            "--id",
            "tester-01",
            "--demo-dir",
            str(demo_dir),
            "--completed-in-minutes",
            "8",
            "--visible-remix",
            "yes",
            "--readme-quickstart",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert code == 1
    assert not (output_dir / "outside-user.entry.json").exists()
