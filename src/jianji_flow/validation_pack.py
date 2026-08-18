from __future__ import annotations

import json
import re
from pathlib import Path


REVIEW_STATUS_RE = re.compile(r"^Status:\s*(pass|warning|fail)\s*$", re.IGNORECASE | re.MULTILINE)
PACK_SCHEMA = "jianji-flow.validation-pack.v1"


def _path_text(path: Path) -> str:
    return path.resolve().as_posix()


def _review_status(path: Path) -> str | None:
    if not path.is_file():
        return None
    match = REVIEW_STATUS_RE.search(path.read_text(encoding="utf-8-sig"))
    return match.group(1).lower() if match else None


def _missing(paths: dict[str, Path]) -> list[str]:
    return [name for name, path in paths.items() if not path.exists()]


def _human_judgment_markdown(
    *,
    name: str,
    kind: str,
    run_dir: Path,
    observed_status: str | None,
) -> str:
    expected = "pass" if kind == "real" else "fail"
    artifact_checks = (
        [
            "- [ ] I watched remix.mp4.",
            "- [ ] The contact sheet supports every voiceover line.",
            "- [ ] The output is a visible remix, not just a new voiceover.",
        ]
        if kind == "real"
        else [
            "- [ ] I confirmed remix.mp4 is absent.",
            "- [ ] review.html explains why the run should fail.",
            "- [ ] The failure protects against bad source material or setup.",
        ]
    )
    return "\n".join(
        [
            "# jianji-flow Human Judgment",
            "",
            f"- pack: {name}",
            f"- kind: {kind}",
            f"- run_dir: {_path_text(run_dir)}",
            f"- observed_review_status: {observed_status or 'unknown'}",
            "- human_judgment: pending",
            "- reason: ",
            "",
            "## Checklist",
            "",
            "- [ ] I opened review.html before making a judgment.",
            *artifact_checks,
            "- [ ] No old subtitles, platform UI, comments, or creator handles remain.",
            "- [ ] Captions are readable on a phone screen.",
            "- [ ] review.md matches what I see.",
            "",
            "Only mark release evidence as manual pass when the observed review status, artifacts, "
            f"and human judgment all support `{expected}`.",
            "",
        ]
    )


def build_validation_pack(
    run_dir: Path,
    *,
    name: str,
    kind: str,
    independent: bool = False,
    opaque_filenames: bool = False,
) -> dict:
    if kind not in {"real", "dirty"}:
        raise ValueError("kind must be real or dirty")
    run_dir = Path(run_dir).resolve()
    review = run_dir / "review.md"
    review_html = run_dir / "review.html"
    manifest = run_dir / "manifest.json"
    remix = run_dir / "remix.mp4"
    contact_sheet = run_dir / "contact-sheet.png"
    observed_status = _review_status(review)

    required = {
        "review": review,
        "review_html": review_html,
        "manifest": manifest,
    }
    if kind == "real":
        required.update({"remix": remix, "contact_sheet": contact_sheet})

    entry = {
        "name": name,
        "review": _path_text(review),
        "manifest": _path_text(manifest),
        "review_html": _path_text(review_html),
        "remix": _path_text(remix),
        "human_judgment": "pending",
    }
    if kind == "real":
        entry.update(
            {
                "contact_sheet": _path_text(contact_sheet),
                "independent": bool(independent),
                "opaque_filenames": bool(opaque_filenames),
            }
        )

    missing = _missing(required)
    return {
        "schema": PACK_SCHEMA,
        "name": name,
        "kind": kind,
        "run_dir": _path_text(run_dir),
        "observed_review_status": observed_status,
        "missing_artifacts": missing,
        "release_gate_list": "real_material_packs" if kind == "real" else "dirty_material_packs",
        "release_gate_entry": entry,
        "human_judgment_markdown": _human_judgment_markdown(
            name=name,
            kind=kind,
            run_dir=run_dir,
            observed_status=observed_status,
        ),
    }


def write_validation_pack(pack: dict, output_dir: Path) -> dict[str, str]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pack_path = output_dir / "validation-pack.json"
    entry_path = output_dir / "release-evidence.entry.json"
    judgment_path = output_dir / "human-judgment.md"
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    entry_path.write_text(
        json.dumps(pack["release_gate_entry"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    judgment_path.write_text(str(pack["human_judgment_markdown"]), encoding="utf-8")
    return {
        "validation_pack": _path_text(pack_path),
        "release_evidence_entry": _path_text(entry_path),
        "human_judgment": _path_text(judgment_path),
    }
