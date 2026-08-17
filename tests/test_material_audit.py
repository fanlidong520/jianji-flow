import json
import shutil
from pathlib import Path

from jianji_flow.cli import main
from jianji_flow.material_audit import audit_material_root, format_material_audit_markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fresh_dir(name: str) -> Path:
    path = PROJECT_ROOT / "out" / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_pack(root: Path, name: str, files: dict[str, bytes]) -> None:
    asset_dir = root / name / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in files.items():
        (asset_dir / filename).write_bytes(payload)


def test_material_audit_groups_renamed_duplicate_packs_without_counting_them_independent():
    root = _fresh_dir("pytest-material-audit-root")
    _write_pack(root, "home-cleaning-kit-v1", {"01-hook.mp4": b"hook", "02-pain.mp4": b"pain"})
    _write_pack(root, "home-cleaning-kit-v2", {"a.mp4": b"hook", "b.mp4": b"pain"})
    _write_pack(root, "kitchen-storage-kit", {"01-hook.mp4": b"kitchen-hook", "02-pain.mp4": b"kitchen-pain"})

    audit = audit_material_root(root)

    assert audit["status"] == "warning"
    assert audit["pack_count"] == 3
    assert audit["independent_pack_count"] == 2
    duplicate_group = audit["duplicate_pack_groups"][0]
    assert duplicate_group["pack_names"] == ["home-cleaning-kit-v1", "home-cleaning-kit-v2"]
    assert "kitchen-storage-kit" not in duplicate_group["pack_names"]


def test_material_audit_markdown_explains_duplicate_groups_plainly():
    root = _fresh_dir("pytest-material-audit-markdown-root")
    _write_pack(root, "kit-a", {"one.mp4": b"same"})
    _write_pack(root, "kit-b", {"renamed.mp4": b"same"})

    markdown = format_material_audit_markdown(audit_material_root(root))

    assert "not independent" in markdown
    assert "kit-a" in markdown
    assert "kit-b" in markdown
    assert "only 1 independent pack" in markdown


def test_material_audit_cli_writes_json_and_markdown_outputs():
    root = _fresh_dir("pytest-material-audit-cli-root")
    output_dir = _fresh_dir("pytest-material-audit-cli-output")
    _write_pack(root, "kit-a", {"one.mp4": b"same"})
    _write_pack(root, "kit-b", {"renamed.mp4": b"same"})

    code = main(["material-audit", "--root", str(root), "--output-dir", str(output_dir)])

    audit = json.loads((output_dir / "material-audit.json").read_text(encoding="utf-8"))
    report = (output_dir / "material-audit.md").read_text(encoding="utf-8")
    assert code == 0
    assert audit["status"] == "warning"
    assert audit["independent_pack_count"] == 1
    assert "not independent" in report


def test_material_audit_fails_when_no_material_packs_exist():
    root = _fresh_dir("pytest-material-audit-empty-root")

    audit = audit_material_root(root)

    assert audit["status"] == "fail"
    assert audit["pack_count"] == 0
    assert "No material packs" in format_material_audit_markdown(audit)
