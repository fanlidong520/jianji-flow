from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_skill_frontmatter_has_required_fields_only():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter = text.split("---", 2)[1]
    keys = [
        line.split(":", 1)[0].strip()
        for line in frontmatter.splitlines()
        if ":" in line
    ]
    assert keys == ["name", "description"]
    assert "name: jianji-flow" in frontmatter
    assert "recipe.json" in frontmatter
    assert "remix.mp4" in frontmatter
    assert "voiceover.wav" in frontmatter


def test_license_is_mit():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Permission is hereby granted" in text


def test_readme_mentions_v0_2_experience_boundaries():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "What v0.2 Does" in text
    assert "It does not create Jianying or CapCut draft projects." in text
    assert "voiceover.wav" in text
    assert "remix.mp4" in text


def test_readme_has_open_source_getting_started_sections():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in (
        "安装",
        "素材怎么准备",
        "怎么判断结果能不能用",
        "适合谁",
        "Known Limitations",
    ):
        assert phrase in text
    assert "pip install -e .[dev]" in text
    assert "py -m pip install -e" in text
    assert "python scripts/run_smoke.py" in text
    assert "review.html" in text


def test_readme_references_demo_contact_sheet_asset():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    asset_path = ROOT / "docs" / "assets" / "home-product-contact-sheet.png"
    assert "docs/assets/home-product-contact-sheet.png" in text
    assert asset_path.exists()
    assert asset_path.stat().st_size > 100_000


def test_readme_documents_v0_3_usability_commands():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "jianji-flow doctor" in text
    assert "jianji-flow demo" in text
    assert "jianji-flow quick" in text
    assert "examples\\reference.mp4" not in text
    assert "fixtures\\scenario-a-product\\reference.mp4" in text
    assert "默认文案只适合清洁类家居样例" in text
    assert "winget install Gyan.FFmpeg" in text
    assert "Ready to run quick draft" in text


def test_skill_documents_quick_start_commands():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "doctor" in text
    assert "demo" in text
    assert "quick" in text
    assert "diagnosis.md" in text
    assert "examples\\reference.mp4" not in text
    assert "fixtures\\scenario-a-product\\reference.mp4" in text


def test_v0_3_validation_record_has_ten_runs():
    text = (ROOT / "docs" / "validation" / "v0.3-usability-runs.md").read_text(encoding="utf-8")
    assert text.count("## Run ") == 10
    assert "usable rough cut" in text
    assert "do not use yet" in text


def test_changelog_documents_public_versions():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "# Changelog" in text
    assert "## 0.2.0" in text
    assert "## 0.1.0" in text
    assert "voiceover.wav" in text


def test_github_ci_runs_unit_tests_without_local_tts_smoke():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python -m pytest -q" in text
    assert "python scripts/run_smoke.py" not in text
    assert "ffmpeg" in text


def test_platform_specific_regression_smoke_is_windows_only():
    text = (ROOT / "tests" / "test_regression_outputs.py").read_text(encoding="utf-8")
    assert "pytest.mark.skipif" in text
    assert 'platform.system() != "Windows"' in text
    assert "Windows local TTS" in text


def test_contributing_guides_small_verified_changes():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "small, focused changes" in text
    assert "python -m pytest -q" in text
    assert "Do not commit generated outputs" in text
