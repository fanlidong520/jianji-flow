from pathlib import Path

from jianji_flow.review import build_review, build_review_html, build_review_markdown, write_review_html, write_review_markdown


def test_review_marks_missing_assets_as_failure():
    recipe = {"segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}]}
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "missing",
                "confidence": 0,
                "missing_reason": "no asset",
            }
        ]
    }

    review = build_review(recipe, matches, remix_path=Path("work/remix.mp4"), captions_path=Path("work/captions.srt"))

    assert review["status"] == "fail"
    assert any("missing" in failure for failure in review["failures"])


def test_review_marks_low_confidence_as_warning():
    recipe = {"segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}]}
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "low_confidence",
                "asset_id": "asset-001",
                "confidence": 0.55,
            }
        ]
    }

    review = build_review(recipe, matches, remix_path=Path("work/remix.mp4"), captions_path=Path("work/captions.srt"))

    assert review["status"] == "warning"
    assert any("low confidence" in warning for warning in review["warnings"])


def test_review_passes_when_all_segments_are_selected():
    recipe = {"segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}]}
    matches = {"matches": [{"id": "match-001", "segment_id": "seg-001", "status": "selected", "asset_id": "asset-001", "confidence": 0.9}]}

    review = build_review(recipe, matches, remix_path=Path("work/remix.mp4"), captions_path=Path("work/captions.srt"))

    assert review["status"] == "pass"
    assert review["failures"] == []
    assert review["warnings"] == []


def test_build_review_markdown_contains_checklist_and_outputs():
    markdown = build_review_markdown(
        {
            "status": "warning",
            "warnings": ["seg-001 low confidence"],
            "failures": [],
            "outputs": {"remix": "work/remix.mp4", "captions": "work/captions.srt"},
            "missing_segments": [],
            "low_confidence_segments": ["seg-001"],
        }
    )

    assert "# jianji-flow Review" in markdown
    assert "Status: warning" in markdown
    assert "work/remix.mp4" in markdown
    assert "seg-001 low confidence" in markdown
    assert "Manual review checklist" in markdown


def test_write_review_markdown_creates_file(tmp_path: Path):
    output = tmp_path / "nested" / "review.md"

    write_review_markdown({"status": "pass", "warnings": [], "failures": [], "outputs": {}}, output)

    assert output.read_text(encoding="utf-8").startswith("# jianji-flow Review")


def test_build_review_html_contains_outputs_and_match_evidence():
    review = {
        "status": "pass",
        "outputs": {
            "remix": "work/remix.mp4",
            "contact_sheet": "work/contact-sheet.png",
            "voiceover": "work/voiceover.wav",
        },
        "warnings": [],
        "failures": [],
    }
    recipe = {
        "segments": [
            {
                "id": "seg-001",
                "match_id": "match-001",
                "caption": "家里难刷角落",
                "start_ms": 0,
                "end_ms": 1000,
            }
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "asset_id": "asset-001",
                "source_path": "assets/hook.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:hook"],
            }
        ]
    }

    html = build_review_html(review, recipe, matches)

    assert "<video" in html
    assert "work/remix.mp4" in html
    assert "work/contact-sheet.png" in html
    assert "work/voiceover.wav" in html
    assert "家里难刷角落" in html
    assert "filename-role:hook" in html


def test_write_review_html_creates_file(tmp_path: Path):
    output = tmp_path / "review.html"

    write_review_html({"status": "pass", "outputs": {}}, {"segments": []}, {"matches": []}, output)

    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")
