import json
import shutil
from pathlib import Path

import pytest

from jianji_flow.cli import main
from jianji_flow.outside_trial import build_outside_trial


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
