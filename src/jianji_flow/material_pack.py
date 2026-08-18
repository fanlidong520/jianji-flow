from __future__ import annotations

import json
from pathlib import Path


MATERIAL_PACK_SCHEMA = "jianji-flow.material-pack.v1"
MATERIAL_PACK_KINDS = ("home-cleaning", "home-storage", "talking-head")


def _path_text(path: Path) -> str:
    return path.resolve().as_posix()


def _validate_pack_name(name: str) -> str:
    clean = str(name).strip()
    if not clean:
        raise ValueError("material-pack requires a non-empty pack name")
    if Path(clean).name != clean or any(separator in clean for separator in ("/", "\\")):
        raise ValueError("material-pack name must be a folder name, not a path")
    return clean


def _validate_kind(kind: str) -> str:
    clean = str(kind).strip()
    if clean not in MATERIAL_PACK_KINDS:
        choices = ", ".join(MATERIAL_PACK_KINDS)
        raise ValueError(f"material-pack kind must be one of: {choices}")
    return clean


def _script_template(kind: str) -> str:
    templates = {
        "home-cleaning": [
            "Hook: This cleaning tool solves one annoying daily mess.",
            "Pain: Show the old wiping or scrubbing process taking too much time.",
            "Demo: Show the product touching the real surface and removing the mess.",
            "Proof: Show a close before-and-after angle in the same room light.",
            "CTA: Keep one at home if this mess appears every week.",
        ],
        "home-storage": [
            "Hook: This storage item makes a messy corner usable again.",
            "Pain: Show the drawer, shelf, or countertop before organizing.",
            "Demo: Put the product in place and load real household items into it.",
            "Proof: Show the same space after storage from a wider angle.",
            "CTA: Use it for one high-frequency area before buying more.",
        ],
        "talking-head": [
            "Hook: State the specific editing problem in one sentence.",
            "Point: Explain what the viewer should notice in the source material.",
            "Evidence: Show a real before-and-after or screen recording.",
            "Limit: Say what the tool cannot judge without human review.",
            "CTA: Ask the viewer to try one small real-material run.",
        ],
    }
    return "\n".join(templates[kind]) + "\n"


def _capture_checklist_markdown(name: str, kind: str) -> str:
    return "\n".join(
        [
            "# Capture Checklist",
            "",
            f"- pack_name: {name}",
            f"- kind: {kind}",
            "- release_gate_status: not_evidence",
            "",
            "## Rules",
            "",
            "- Record newly recorded footage for this pack.",
            "- Use newly recorded footage, not renamed copies from an older pack; renamed copies never count as new evidence.",
            "- Put source videos in `assets/`.",
            "- Keep old platform subtitles, creator handles, comments, and app UI out of source clips.",
            "- Use real product actions or real talking-head footage, not placeholder color clips.",
            "- This scaffold does not prove material independence, edit quality, or outside-user success.",
            "",
            "## Minimum Product Pack",
            "",
            "- 01-hook: the first visual reason to watch.",
            "- 02-pain: the messy or inconvenient before state.",
            "- 03-demo: product in use with real hands or real environment.",
            "- 04-proof: close before/after or result detail.",
            "- 05-cta: final product or use-case shot.",
            "",
            "## Minimum Talking-Head Pack",
            "",
            "- one continuous talking-head source, plus at least three supporting screen or B-roll clips.",
            "- script.txt should match what is actually said.",
            "",
            "## Next Verification",
            "",
            "Run `material-audit`, then run `quick`, then package the result with `evidence-pack` only after a real MP4 and human review exist.",
            "",
        ]
    )


def _readme_markdown(root: Path, name: str, kind: str) -> str:
    pack_dir = root / name
    return "\n".join(
        [
            "# Material Pack Scaffold",
            "",
            "This folder is a preparation template, not release evidence.",
            "",
            "## Fill This Folder",
            "",
            "- Put real video files in `assets/`.",
            "- Replace `script.txt` with the exact script or narration for this pack.",
            "- Use the checklist before running the editor.",
            "",
            "## Suggested Commands",
            "",
            "```powershell",
            f"python -m jianji_flow material-audit --root {_path_text(root)} --output-dir out\\material-audit-{name}",
            f"python -m jianji_flow quick --reference path\\reference.mp4 --assets {_path_text(pack_dir / 'assets')} --script {_path_text(pack_dir / 'script.txt')} --work-dir out\\quick-{name}",
            f"python -m jianji_flow evidence-pack --run-dir out\\quick-{name} --name {name} --kind real --output-dir out\\evidence-{name}",
            "```",
            "",
            "Only add `--independent` or use the generated evidence in the release gate after `material-audit`, `quick`, and human review all support that claim.",
            f"This pack kind is `{kind}`.",
            "",
        ]
    )


def build_material_pack_scaffold(root: Path, *, name: str, kind: str) -> dict:
    root = Path(root).resolve()
    name = _validate_pack_name(name)
    kind = _validate_kind(kind)
    pack_dir = root / name
    assets_dir = pack_dir / "assets"
    readme = _readme_markdown(root, name, kind)
    checklist = _capture_checklist_markdown(name, kind)
    script = _script_template(kind)
    return {
        "schema": MATERIAL_PACK_SCHEMA,
        "name": name,
        "kind": kind,
        "release_gate_status": "not_evidence",
        "root": _path_text(root),
        "pack_dir": _path_text(pack_dir),
        "assets_dir": _path_text(assets_dir),
        "files": {
            "readme": _path_text(pack_dir / "README.md"),
            "capture_checklist": _path_text(pack_dir / "capture-checklist.md"),
            "script": _path_text(pack_dir / "script.txt"),
            "metadata": _path_text(pack_dir / "material-pack.json"),
        },
        "readme_markdown": readme,
        "capture_checklist_markdown": checklist,
        "script_text": script,
        "next_commands": [
            "material-audit",
            "quick",
            "evidence-pack after real run and human review",
        ],
    }


def write_material_pack_scaffold(scaffold: dict) -> dict[str, str]:
    pack_dir = Path(str(scaffold["pack_dir"]))
    if pack_dir.exists():
        raise FileExistsError(f"material pack already exists: {pack_dir}")
    assets_dir = Path(str(scaffold["assets_dir"]))
    assets_dir.mkdir(parents=True, exist_ok=False)
    files = scaffold["files"]
    readme_path = Path(str(files["readme"]))
    checklist_path = Path(str(files["capture_checklist"]))
    script_path = Path(str(files["script"]))
    metadata_path = Path(str(files["metadata"]))
    readme_path.write_text(str(scaffold["readme_markdown"]), encoding="utf-8")
    checklist_path.write_text(str(scaffold["capture_checklist_markdown"]), encoding="utf-8")
    script_path.write_text(str(scaffold["script_text"]), encoding="utf-8")
    metadata_path.write_text(json.dumps(scaffold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "pack_dir": _path_text(pack_dir),
        "assets_dir": _path_text(assets_dir),
        "readme": _path_text(readme_path),
        "capture_checklist": _path_text(checklist_path),
        "script": _path_text(script_path),
        "metadata": _path_text(metadata_path),
    }
