import importlib
import importlib.util
import json
import shutil
from pathlib import Path

from jianji_flow.cli import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fresh_dir(name: str) -> Path:
    path = PROJECT_ROOT / "out" / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_material_pack_builder_marks_scaffold_as_not_release_evidence():
    assert importlib.util.find_spec("jianji_flow.material_pack") is not None
    module = importlib.import_module("jianji_flow.material_pack")

    scaffold = module.build_material_pack_scaffold(
        Path("E:/jianji-sucai"),
        name="home-storage-real-02",
        kind="home-storage",
    )

    assert scaffold["schema"] == "jianji-flow.material-pack.v1"
    assert scaffold["name"] == "home-storage-real-02"
    assert scaffold["release_gate_status"] == "not_evidence"
    assert "newly recorded" in scaffold["capture_checklist_markdown"]
    assert "not renamed copies" in scaffold["capture_checklist_markdown"]
    assert "material-audit" in scaffold["readme_markdown"]
    assert "quick" in scaffold["readme_markdown"]
    assert "evidence-pack" in scaffold["readme_markdown"]


def test_material_pack_cli_creates_assets_script_and_checklist():
    root = _fresh_dir("pytest-material-pack-root")

    code = main(
        [
            "material-pack",
            "--root",
            str(root),
            "--name",
            "home-storage-real-02",
            "--kind",
            "home-storage",
        ]
    )

    pack_dir = root / "home-storage-real-02"
    assert code == 0
    assert (pack_dir / "assets").is_dir()
    assert (pack_dir / "script.txt").exists()
    assert (pack_dir / "README.md").exists()
    assert (pack_dir / "capture-checklist.md").exists()
    assert (pack_dir / "material-pack.json").exists()
    metadata = json.loads((pack_dir / "material-pack.json").read_text(encoding="utf-8"))
    checklist = (pack_dir / "capture-checklist.md").read_text(encoding="utf-8")
    readme = (pack_dir / "README.md").read_text(encoding="utf-8")
    script = (pack_dir / "script.txt").read_text(encoding="utf-8")
    assert metadata["release_gate_status"] == "not_evidence"
    assert "newly recorded" in checklist
    assert "not renamed copies" in checklist
    assert "material-audit" in readme
    assert "quick" in readme
    assert "evidence-pack" in readme
    assert "storage" in script.lower()


def test_material_pack_cli_refuses_existing_pack_folder():
    root = _fresh_dir("pytest-material-pack-existing-root")
    (root / "home-cleaning-real-03").mkdir(parents=True)

    code = main(
        [
            "material-pack",
            "--root",
            str(root),
            "--name",
            "home-cleaning-real-03",
            "--kind",
            "home-cleaning",
        ]
    )

    assert code == 1
