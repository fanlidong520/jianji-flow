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
