from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REVIEW_STATUS_RE = re.compile(r"^Status:\s*(pass|warning|fail)\s*$", re.IGNORECASE | re.MULTILINE)
QUALITY_STATUS_KEYS = ("smoke", "p0", "skill_validation", "clean_install")


def _resolve_path(value: Any, repo_root: Path) -> Path:
    path = Path(str(value or ""))
    return path if path.is_absolute() else repo_root / path


def _review_status(value: Any, repo_root: Path) -> str | None:
    path = _resolve_path(value, repo_root)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8-sig")
    match = REVIEW_STATUS_RE.search(text)
    return match.group(1).lower() if match else None


def _manifest_identity(value: Any, repo_root: Path) -> tuple[str | None, str | None]:
    path = _resolve_path(value, repo_root)
    if not path.is_file():
        return None, "manifest file is missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None, "manifest file is not valid JSON"
    assets = data.get("assets") if isinstance(data, dict) else None
    if not isinstance(assets, list):
        return None, "manifest has no assets list"
    hashes = sorted(
        str(asset.get("sha256", "")).strip().casefold()
        for asset in assets
        if isinstance(asset, dict) and str(asset.get("sha256", "")).strip()
    )
    if not hashes:
        return None, "manifest has no SHA-256 asset identities"
    identity = hashlib.sha256("\n".join(hashes).encode("ascii", errors="ignore")).hexdigest()
    return identity, None


def _is_pass(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() == "pass"


def _is_finite_minutes(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def evaluate_gate(evidence: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    blockers: list[str] = []
    checks: dict[str, Any] = {}

    quality = evidence.get("quality")
    if not isinstance(quality, dict):
        quality = {}
        blockers.append("quality evidence is missing")

    full_tests = quality.get("full_tests")
    full_tests_pass = (
        isinstance(full_tests, dict)
        and _is_pass(full_tests.get("status"))
        and isinstance(full_tests.get("passed"), int)
        and full_tests.get("passed", 0) > 0
    )
    checks["full_tests"] = int(full_tests.get("passed", 0)) if isinstance(full_tests, dict) else 0
    if not full_tests_pass:
        blockers.append("full test evidence is missing or not passing")

    for key in QUALITY_STATUS_KEYS:
        passed = _is_pass(quality.get(key))
        checks[key] = passed
        if not passed:
            blockers.append(f"{key} evidence is missing or not passing")

    real_packs = evidence.get("real_material_packs")
    if not isinstance(real_packs, list):
        real_packs = []
    valid_real_names: list[str] = []
    opaque_real_names: list[str] = []
    seen_real_names: set[str] = set()
    seen_real_reviews: set[str] = set()
    seen_real_identities: set[str] = set()
    for pack in real_packs:
        if not isinstance(pack, dict):
            blockers.append("a real-material pack entry is not an object")
            continue
        name = str(pack.get("name", "")).strip() or "unnamed real-material pack"
        reasons: list[str] = []
        name_key = name.casefold()
        if name_key in seen_real_names:
            reasons.append("duplicate pack name")
        seen_real_names.add(name_key)
        review_path = _resolve_path(pack.get("review"), repo_root)
        review_key = review_path.resolve().as_posix().casefold()
        if review_key in seen_real_reviews:
            reasons.append("duplicate review path")
        seen_real_reviews.add(review_key)
        material_identity, identity_error = _manifest_identity(pack.get("manifest"), repo_root)
        if identity_error:
            reasons.append(identity_error)
        elif material_identity in seen_real_identities:
            reasons.append("duplicate material identity")
        if material_identity:
            seen_real_identities.add(material_identity)
        observed_status = _review_status(pack.get("review"), repo_root)
        if not review_path.is_file():
            reasons.append("review file is missing")
        elif observed_status != "pass":
            reasons.append(f"review status is {observed_status or 'unknown'}, expected pass")
        if pack.get("independent") is not True:
            reasons.append("pack is not marked independent")
        if str(pack.get("human_judgment", "")).casefold() != "pass":
            reasons.append("human judgment is not pass")
        if reasons:
            blockers.append(f"{name}: " + "; ".join(reasons))
            continue
        valid_real_names.append(name)
        if pack.get("opaque_filenames") is True:
            opaque_real_names.append(name)

    checks["real_material_passes"] = len(valid_real_names)
    checks["opaque_filename_passes"] = len(opaque_real_names)
    if len(valid_real_names) < 3:
        blockers.append(
            f"only {len(valid_real_names)} independent real-material pass(es); three independent passes are required"
        )
    if not opaque_real_names:
        blockers.append("no independent real-material pass uses opaque filenames")

    dirty_packs = evidence.get("dirty_material_packs")
    if not isinstance(dirty_packs, list):
        dirty_packs = []
    valid_dirty = 0
    for pack in dirty_packs:
        if not isinstance(pack, dict):
            blockers.append("a dirty-material pack entry is not an object")
            continue
        name = str(pack.get("name", "")).strip() or "unnamed dirty-material pack"
        observed_status = _review_status(pack.get("review"), repo_root)
        reasons: list[str] = []
        _, identity_error = _manifest_identity(pack.get("manifest"), repo_root)
        if identity_error:
            reasons.append(identity_error)
        if not _resolve_path(pack.get("review"), repo_root).is_file():
            reasons.append("review file is missing")
        elif observed_status != "fail":
            reasons.append(f"review status is {observed_status or 'unknown'}, expected fail")
        if str(pack.get("human_judgment", "")).casefold() != "fail":
            reasons.append("human judgment is not fail")
        if reasons:
            blockers.append(f"{name}: " + "; ".join(reasons))
        else:
            valid_dirty += 1
    checks["dirty_material_failures"] = valid_dirty
    if valid_dirty == 0:
        blockers.append("no dirty-material pack is verified as a correct fail")

    outside_users = evidence.get("outside_users")
    if not isinstance(outside_users, list):
        outside_users = []
    users_within_limit = 0
    users_with_visible_remix = 0
    seen_user_ids: set[str] = set()
    for user in outside_users:
        if not isinstance(user, dict):
            continue
        user_id = str(user.get("id", "")).strip()
        label = user_id or "unnamed outside user"
        if user.get("readme_quickstart") is not True:
            blockers.append(f"{label}: README quickstart is not recorded")
            continue
        if not user_id:
            blockers.append("unnamed outside user: a stable id is required")
            continue
        if user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)
        minutes = user.get("completed_in_minutes")
        if _is_finite_minutes(minutes):
            if minutes <= 10:
                users_within_limit += 1
        if user.get("visible_remix") is True:
            users_with_visible_remix += 1
    checks["outside_users"] = len(seen_user_ids)
    checks["outside_users_within_10_minutes"] = users_within_limit
    checks["outside_users_judged_visible_remix"] = users_with_visible_remix
    if len(seen_user_ids) < 5:
        blockers.append(f"only {len(seen_user_ids)} outside users recorded; five are required")
    if users_within_limit < 4:
        blockers.append(f"only {users_within_limit} outside users finished within 10 minutes; four are required")
    if users_with_visible_remix < 4:
        blockers.append(
            f"only {users_with_visible_remix} outside users judged the result visibly re-edited; four are required"
        )

    known_false_passes = evidence.get("known_false_passes")
    if not isinstance(known_false_passes, list):
        known_false_passes = []
    checks["known_false_passes"] = len(known_false_passes)
    if known_false_passes:
        blockers.append(f"{len(known_false_passes)} known false pass(es) remain")

    readme_path = _resolve_path(evidence.get("readme", "README.md"), repo_root)
    readme_text = readme_path.read_text(encoding="utf-8-sig") if readme_path.is_file() else ""
    checks["readme_honest_warning_example"] = "warning" in readme_text.casefold() and "review.md" in readme_text
    if not checks["readme_honest_warning_example"]:
        blockers.append("README is missing an honest warning/review example")

    return {
        "status": "pass" if not blockers else "blocked",
        "checks": checks,
        "valid_real_material_packs": valid_real_names,
        "opaque_filename_packs": opaque_real_names,
        "blockers": blockers,
    }


def _report_markdown(result: dict[str, Any]) -> str:
    lines = ["# Release Gate", "", f"Status: {result['status']}", "", "## Checks"]
    for key, value in result.get("checks", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Blockers"])
    blockers = result.get("blockers", [])
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the auditable jianji-flow release gate")
    parser.add_argument("--evidence", required=True, help="JSON evidence ledger")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--report-dir", default="out/release-gate")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    evidence_path = _resolve_path(args.evidence, repo_root)
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"release gate input error: {evidence_path}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(evidence, dict):
        print("release gate input error: evidence must be a JSON object", file=sys.stderr)
        return 2

    result = evaluate_gate(evidence, repo_root=repo_root)
    report_dir = _resolve_path(args.report_dir, repo_root)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "release-gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (report_dir / "release-gate.md").write_text(_report_markdown(result), encoding="utf-8")
    print(f"release gate: {result['status']}")
    for blocker in result["blockers"]:
        print(f"- {blocker}")
    print(f"report: {report_dir / 'release-gate.md'}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
