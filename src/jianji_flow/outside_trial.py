from __future__ import annotations

import json
import math
from pathlib import Path


TRIAL_SCHEMA = "jianji-flow.outside-trial.v1"
TRIAL_RESULT_SCHEMA = "jianji-flow.outside-trial-result.v1"


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


def _stable_user_id(user_id: str) -> str:
    user_id = str(user_id).strip()
    if not user_id:
        raise ValueError("outside trial requires a stable tester id")
    return user_id


def _finite_minutes(value: float | int) -> float | int:
    minutes = float(value)
    if not math.isfinite(minutes) or minutes < 0:
        raise ValueError("completed_in_minutes must be a non-negative finite number")
    return int(minutes) if minutes.is_integer() else minutes


def _review_status(review_path: Path) -> str:
    for line in review_path.read_text(encoding="utf-8-sig").splitlines():
        if line.casefold().startswith("status:"):
            return line.split(":", 1)[1].strip()
    return ""


def _artifact_check(demo_dir: Path) -> dict:
    required = ("review.md", "review.html", "remix.mp4", "contact-sheet.png")
    artifacts = {}
    missing = []
    for name in required:
        path = demo_dir / name
        ok = path.is_file() and path.stat().st_size > 0
        artifacts[name] = {"path": _path_text(path), "exists": path.is_file(), "non_empty": ok}
        if not ok:
            missing.append(name)
    return {"status": "fail" if missing else "pass", "missing": missing, "artifacts": artifacts}


def _trial_result_markdown(result: dict) -> str:
    entry = result["release_gate_entry"]
    artifact_check = result["artifact_check"]
    return "\n".join(
        [
            "# Outside Trial Result",
            "",
            f"- tester_id: {entry['id']}",
            f"- readme_quickstart: {str(entry['readme_quickstart']).lower()}",
            f"- completed_in_minutes: {entry['completed_in_minutes']}",
            f"- visible_remix: {str(entry['visible_remix']).lower()}",
            f"- review_status: {entry['review_status']}",
            f"- artifact_status: {artifact_check['status']}",
            "",
            "This is a structured record of an explicit tester judgment.",
            "Do not set visible_remix to true unless the tester said the result looked visibly re-edited.",
            "Do not copy this into release evidence unless the tester actually used the README quickstart path.",
            "",
        ]
    )


def build_outside_trial_result(
    user_id: str,
    demo_dir: Path,
    *,
    completed_in_minutes: float | int,
    visible_remix: bool,
    readme_quickstart: bool,
    blocked_step: str = "",
    notes: str = "",
) -> dict:
    user_id = _stable_user_id(user_id)
    demo_dir = Path(demo_dir).resolve()
    if not demo_dir.is_dir():
        raise NotADirectoryError(f"trial demo directory does not exist: {demo_dir}")
    artifact_check = _artifact_check(demo_dir)
    if artifact_check["status"] != "pass":
        missing = ", ".join(str(item) for item in artifact_check["missing"])
        raise ValueError(f"missing trial artifact(s): {missing}")
    entry = {
        "id": user_id,
        "readme_quickstart": bool(readme_quickstart),
        "completed_in_minutes": _finite_minutes(completed_in_minutes),
        "visible_remix": bool(visible_remix),
        "review_status": _review_status(demo_dir / "review.md"),
        "blocked_step": str(blocked_step),
        "notes": str(notes),
    }
    result = {
        "schema": TRIAL_RESULT_SCHEMA,
        "release_gate_list": "outside_users",
        "demo_dir": _path_text(demo_dir),
        "artifact_check": artifact_check,
        "release_gate_entry": entry,
    }
    result["result_markdown"] = _trial_result_markdown(result)
    return result


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


def write_outside_trial_result(result: dict, output_dir: Path) -> dict[str, str]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "outside-trial-result.json"
    entry_path = output_dir / "outside-user.entry.json"
    markdown_path = output_dir / "outside-trial-result.md"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    entry_path.write_text(
        json.dumps(result["release_gate_entry"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(str(result["result_markdown"]), encoding="utf-8")
    return {
        "outside_trial_result": _path_text(result_path),
        "outside_user_entry": _path_text(entry_path),
        "result_markdown": _path_text(markdown_path),
    }
