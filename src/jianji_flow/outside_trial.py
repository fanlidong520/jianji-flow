from __future__ import annotations

import json
from pathlib import Path


TRIAL_SCHEMA = "jianji-flow.outside-trial.v1"


def _path_text(path: Path) -> str:
    return path.resolve().as_posix()


def _trial_markdown(user_id: str) -> str:
    return "\n".join(
        [
            "# Outside User Trial",
            "",
            f"- tester_id: {user_id}",
            "- readme_quickstart: false",
            "- completed_in_minutes: ",
            "- visible_remix: ",
            "- review_status: ",
            "- blocked_step: ",
            "- notes: ",
            "",
            "## Commands To Run",
            "",
            "```powershell",
            "jianji-flow doctor --work-dir out\\trial-doctor",
            "jianji-flow demo --work-dir out\\trial-demo",
            "```",
            "",
            "## Open After Running",
            "",
            "- out\\trial-demo\\review.html",
            "- out\\trial-demo\\remix.mp4",
            "- out\\trial-demo\\contact-sheet.png",
            "",
            "## Questions",
            "",
            "1. Did you reach a playable MP4 without developer help?",
            "2. Did the contact sheet make it obvious that the pictures changed?",
            "3. What was the first confusing or blocking step?",
            "4. Would you use this on another video?",
            "",
            "Record the raw answer and exact command used.",
            "Do not turn this into release evidence until the tester actually used the README path.",
            "",
        ]
    )


def build_outside_trial(user_id: str) -> dict:
    user_id = str(user_id).strip()
    if not user_id:
        raise ValueError("outside trial requires a stable tester id")
    entry = {
        "id": user_id,
        "readme_quickstart": False,
        "completed_in_minutes": None,
        "visible_remix": None,
        "review_status": "",
        "blocked_step": "",
        "notes": "",
    }
    return {
        "schema": TRIAL_SCHEMA,
        "release_gate_list": "outside_users",
        "release_gate_entry": entry,
        "trial_markdown": _trial_markdown(user_id),
    }


def write_outside_trial(trial: dict, output_dir: Path) -> dict[str, str]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    trial_path = output_dir / "outside-trial.json"
    entry_path = output_dir / "outside-user.entry.json"
    markdown_path = output_dir / "outside-user-trial.md"
    trial_path.write_text(json.dumps(trial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    entry_path.write_text(
        json.dumps(trial["release_gate_entry"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(str(trial["trial_markdown"]), encoding="utf-8")
    return {
        "outside_trial": _path_text(trial_path),
        "outside_user_entry": _path_text(entry_path),
        "trial_markdown": _path_text(markdown_path),
    }
