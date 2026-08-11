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


def test_contributing_guides_small_verified_changes():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "small, focused changes" in text
    assert "python -m pytest -q" in text
    assert "Do not commit generated outputs" in text
