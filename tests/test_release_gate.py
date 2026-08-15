from __future__ import annotations

import json
from pathlib import Path

from scripts.check_release_gate import evaluate_gate, main


def _review(path: Path, status: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Review\n\nStatus: {status}\n", encoding="utf-8")
    return path.as_posix()


def _manifest(path: Path, *sha256: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"assets": [{"sha256": value} for value in sha256]}),
        encoding="utf-8",
    )
    return path.as_posix()


def _real_artifacts(root: Path, status: str = "pass") -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    review_html = root / "review.html"
    review_html.write_text(f"<html>Status: {status}</html>\n", encoding="utf-8")
    remix = root / "remix.mp4"
    remix.write_bytes(b"remix")
    contact_sheet = root / "contact-sheet.png"
    contact_sheet.write_bytes(b"contact-sheet")
    return {
        "review_html": review_html.as_posix(),
        "remix": remix.as_posix(),
        "contact_sheet": contact_sheet.as_posix(),
    }


def _dirty_artifacts(root: Path) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    review_html = root / "review.html"
    review_html.write_text("<html>Status: fail</html>\n", encoding="utf-8")
    return {
        "review_html": review_html.as_posix(),
        "remix": (root / "remix.mp4").as_posix(),
    }


def _quality() -> dict:
    return {
        "full_tests": {"status": "pass", "passed": 403},
        "smoke": "pass",
        "p0": "pass",
        "skill_validation": "pass",
        "clean_install": "pass",
    }


def test_release_gate_blocks_until_real_packs_and_outside_users_are_verified(tmp_path: Path):
    evidence = {
        "quality": _quality(),
        "real_material_packs": [
            {
                "name": "one-clean-pack",
                "review": _review(tmp_path / "pack-1" / "review.md", "pass"),
                "manifest": _manifest(tmp_path / "pack-1" / "manifest.json", "sha-one"),
                **_real_artifacts(tmp_path / "pack-1"),
                "independent": True,
                "opaque_filenames": True,
                "human_judgment": "pass",
            }
        ],
        "dirty_material_packs": [],
        "outside_users": [],
        "known_false_passes": [],
        "readme": "README.md",
    }

    result = evaluate_gate(evidence, repo_root=tmp_path)

    assert result["status"] == "blocked"
    assert any("three independent" in item for item in result["blockers"])
    assert any("outside users" in item for item in result["blockers"])


def test_release_gate_requires_rendered_real_pack_artifacts(tmp_path: Path):
    evidence = {
        "quality": _quality(),
        "real_material_packs": [
            {
                "name": "missing-output-pack",
                "review": _review(tmp_path / "pack" / "review.md", "pass"),
                "manifest": _manifest(tmp_path / "pack" / "manifest.json", "sha-one"),
                "independent": True,
                "opaque_filenames": True,
                "human_judgment": "pass",
            }
        ],
        "dirty_material_packs": [],
        "outside_users": [],
        "known_false_passes": [],
        "readme": "README.md",
    }

    result = evaluate_gate(evidence, repo_root=tmp_path)

    assert result["checks"]["real_material_passes"] == 0
    blocker_text = "\n".join(result["blockers"])
    assert "review_html file is missing" in blocker_text
    assert "remix file is missing" in blocker_text
    assert "contact_sheet file is missing" in blocker_text


def test_release_gate_passes_only_with_matching_review_and_human_evidence(tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text("Run the workflow. Review warning output in review.md.", encoding="utf-8")
    real_packs = []
    for index in range(3):
        real_packs.append(
            {
                "name": f"clean-pack-{index}",
                "review": _review(tmp_path / f"pack-{index}" / "review.md", "pass"),
                "manifest": _manifest(tmp_path / f"pack-{index}" / "manifest.json", f"sha-{index}"),
                **_real_artifacts(tmp_path / f"pack-{index}"),
                "independent": True,
                "opaque_filenames": index == 0,
                "human_judgment": "pass",
            }
        )
    users = [
        {
            "id": f"user-{index}",
            "readme_quickstart": True,
            "completed_in_minutes": 8 if index < 4 else 12,
            "visible_remix": index < 4,
        }
        for index in range(5)
    ]
    evidence = {
        "quality": _quality(),
        "real_material_packs": real_packs,
        "dirty_material_packs": [
            {
                "name": "dirty-pack",
                "review": _review(tmp_path / "dirty" / "review.md", "fail"),
                "manifest": _manifest(tmp_path / "dirty" / "manifest.json", "sha-dirty"),
                **_dirty_artifacts(tmp_path / "dirty"),
                "human_judgment": "fail",
            }
        ],
        "outside_users": users,
        "known_false_passes": [],
        "readme": "README.md",
    }

    result = evaluate_gate(evidence, repo_root=tmp_path)

    assert result["status"] == "pass"
    assert result["checks"]["real_material_passes"] == 3
    assert result["checks"]["outside_users_within_10_minutes"] == 4


def test_release_gate_blocks_when_review_status_disagrees_with_evidence(tmp_path: Path):
    evidence = {
        "quality": _quality(),
        "real_material_packs": [
            {
                "name": "misreported-pack",
                "review": _review(tmp_path / "pack" / "review.md", "warning"),
                "manifest": _manifest(tmp_path / "pack" / "manifest.json", "sha-warning"),
                **_real_artifacts(tmp_path / "pack", "warning"),
                "independent": True,
                "opaque_filenames": True,
                "human_judgment": "pass",
            }
        ],
        "dirty_material_packs": [],
        "outside_users": [],
        "known_false_passes": [],
        "readme": "README.md",
    }

    result = evaluate_gate(evidence, repo_root=tmp_path)

    assert result["status"] == "blocked"
    assert any("misreported-pack" in item and "pass" in item for item in result["blockers"])


def test_release_gate_cli_writes_machine_and_human_reports(tmp_path: Path):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps({"quality": {}}), encoding="utf-8")
    report_dir = tmp_path / "report"

    code = main(
        [
            "--evidence",
            str(evidence_path),
            "--repo-root",
            str(tmp_path),
            "--report-dir",
            str(report_dir),
        ]
    )

    assert code == 1
    assert json.loads((report_dir / "release-gate.json").read_text(encoding="utf-8"))["status"] == "blocked"
    assert "Status: blocked" in (report_dir / "release-gate.md").read_text(encoding="utf-8")


def test_release_gate_does_not_count_one_review_as_multiple_independent_packs(tmp_path: Path):
    review = _review(tmp_path / "one-pack" / "review.md", "pass")
    real_packs = [
        {
            "name": f"alias-{index}",
            "review": review,
            "manifest": _manifest(tmp_path / "one-pack" / "manifest.json", "sha-same"),
            **_real_artifacts(tmp_path / "one-pack"),
            "independent": True,
            "opaque_filenames": index == 0,
            "human_judgment": "pass",
        }
        for index in range(3)
    ]
    evidence = {
        "quality": _quality(),
        "real_material_packs": real_packs,
        "dirty_material_packs": [],
        "outside_users": [],
        "known_false_passes": [],
        "readme": "README.md",
    }

    result = evaluate_gate(evidence, repo_root=tmp_path)

    assert result["checks"]["real_material_passes"] == 1
    assert any("duplicate review path" in item for item in result["blockers"])


def test_release_gate_does_not_count_same_manifest_as_independent_packs(tmp_path: Path):
    real_packs = []
    for index in range(3):
        real_packs.append(
            {
                "name": f"same-material-{index}",
                "review": _review(tmp_path / f"review-{index}.md", "pass"),
                "manifest": _manifest(tmp_path / "shared-manifest.json", "sha-shared"),
                **_real_artifacts(tmp_path / f"same-material-{index}"),
                "independent": True,
                "opaque_filenames": index == 0,
                "human_judgment": "pass",
            }
        )
    evidence = {
        "quality": _quality(),
        "real_material_packs": real_packs,
        "dirty_material_packs": [],
        "outside_users": [],
        "known_false_passes": [],
        "readme": "README.md",
    }

    result = evaluate_gate(evidence, repo_root=tmp_path)

    assert result["checks"]["real_material_passes"] == 1
    assert any("duplicate material identity" in item for item in result["blockers"])


def test_release_gate_requires_manifest_for_dirty_pack_evidence(tmp_path: Path):
    evidence = {
        "quality": _quality(),
        "real_material_packs": [],
        "dirty_material_packs": [
            {
                "name": "untraceable-dirty-pack",
                "review": _review(tmp_path / "dirty" / "review.md", "fail"),
                "human_judgment": "fail",
            }
        ],
        "outside_users": [],
        "known_false_passes": [],
        "readme": "README.md",
    }

    result = evaluate_gate(evidence, repo_root=tmp_path)

    assert result["checks"]["dirty_material_failures"] == 0
    assert any("manifest file is missing" in item for item in result["blockers"])


def test_release_gate_does_not_count_users_who_did_not_try_readme_quickstart(tmp_path: Path):
    evidence = {
        "quality": _quality(),
        "real_material_packs": [],
        "dirty_material_packs": [],
        "outside_users": [
            {"id": "user-1", "completed_in_minutes": 5, "visible_remix": True},
        ],
        "known_false_passes": [],
        "readme": "README.md",
    }

    result = evaluate_gate(evidence, repo_root=tmp_path)

    assert result["checks"]["outside_users"] == 0
    assert any("README quickstart" in item for item in result["blockers"])
