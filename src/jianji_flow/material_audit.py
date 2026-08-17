from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jianji_flow.media_scan import SUPPORTED_EXTENSIONS


AUDIT_SCHEMA = "jianji-flow.material-audit.v1"


def _path_text(path: Path) -> str:
    return path.resolve().as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _media_files(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )


def _pack_asset_root(pack_dir: Path) -> Path:
    asset_dir = pack_dir / "assets"
    return asset_dir if asset_dir.is_dir() else pack_dir


def _pack_record(pack_dir: Path) -> dict | None:
    asset_root = _pack_asset_root(pack_dir)
    files = _media_files(asset_root)
    if not files:
        return None
    assets = [
        {
            "path": _path_text(path),
            "relative_path": path.relative_to(asset_root).as_posix(),
            "sha256": _sha256(path),
        }
        for path in files
    ]
    hashes = sorted(asset["sha256"] for asset in assets)
    identity = hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()
    return {
        "name": pack_dir.name,
        "path": _path_text(pack_dir),
        "asset_root": _path_text(asset_root),
        "asset_count": len(assets),
        "material_identity": identity,
        "assets": assets,
    }


def audit_material_root(root: Path) -> dict:
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"material root does not exist: {root}")
    packs = [
        record
        for child in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.casefold())
        if (record := _pack_record(child)) is not None
    ]
    by_identity: dict[str, list[dict]] = {}
    for pack in packs:
        by_identity.setdefault(str(pack["material_identity"]), []).append(pack)
    duplicate_groups = [
        {
            "material_identity": identity,
            "pack_names": [str(pack["name"]) for pack in group],
            "pack_paths": [str(pack["path"]) for pack in group],
        }
        for identity, group in by_identity.items()
        if len(group) > 1
    ]
    independent_count = len(by_identity)
    status = "fail" if not packs else "warning" if duplicate_groups else "pass"
    return {
        "schema": AUDIT_SCHEMA,
        "root": _path_text(root),
        "status": status,
        "pack_count": len(packs),
        "independent_pack_count": independent_count,
        "packs": packs,
        "duplicate_pack_groups": duplicate_groups,
    }


def format_material_audit_markdown(audit: dict) -> str:
    lines = [
        "# Material Audit",
        "",
        f"Status: {audit.get('status', 'unknown')}",
        f"Material root: {audit.get('root', '')}",
        f"Pack folders with media: {audit.get('pack_count', 0)}",
        f"Independent material identities: {audit.get('independent_pack_count', 0)}",
        "",
    ]
    packs = audit.get("packs", [])
    if not packs:
        lines.append("No material packs with local video files were found.")
        return "\n".join(lines) + "\n"
    duplicate_groups = audit.get("duplicate_pack_groups", [])
    if duplicate_groups:
        lines.extend(
            [
                "## Duplicate Pack Groups",
                "",
                "These folders are not independent for release-gate evidence because their media file hashes match.",
            ]
        )
        for group in duplicate_groups:
            names = ", ".join(str(name) for name in group.get("pack_names", []))
            lines.append(f"- {names} are not independent.")
        lines.append("")
    lines.extend(["## Packs", ""])
    for pack in packs:
        lines.append(
            f"- {pack.get('name')}: {pack.get('asset_count')} media file(s), identity `{pack.get('material_identity')}`"
        )
    count = audit.get("independent_pack_count", 0)
    suffix = "pack" if count == 1 else "packs"
    lines.extend(
        [
            "",
            f"Result: only {count} independent {suffix} can be counted from this root.",
            "Use this before release evidence packaging so renamed copies are not counted as separate real-material packs.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_material_audit(audit: dict, output_dir: Path) -> dict[str, str]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "material-audit.json"
    markdown_path = output_dir / "material-audit.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(format_material_audit_markdown(audit), encoding="utf-8")
    return {
        "json": _path_text(json_path),
        "markdown": _path_text(markdown_path),
    }
