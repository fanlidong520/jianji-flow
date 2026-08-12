from pathlib import Path
from PIL import Image

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

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/remix.mp4"),
        captions_path=Path("work/captions.srt"),
        check_artifacts=False,
    )

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

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/remix.mp4"),
        captions_path=Path("work/captions.srt"),
        check_artifacts=False,
    )

    assert review["status"] == "warning"
    assert any("low confidence" in warning for warning in review["warnings"])


def test_review_passes_when_all_segments_are_selected():
    recipe = {"segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}]}
    matches = {"matches": [{"id": "match-001", "segment_id": "seg-001", "status": "selected", "asset_id": "asset-001", "confidence": 0.9}]}

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/remix.mp4"),
        captions_path=Path("work/captions.srt"),
        check_artifacts=False,
    )

    assert review["status"] == "pass"
    assert review["failures"] == []
    assert review["warnings"] == []


def test_review_fails_when_rendered_video_is_missing():
    recipe = {"duration_ms": 1000, "segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}]}
    matches = {"matches": [{"id": "match-001", "segment_id": "seg-001", "status": "selected", "asset_id": "asset-001", "confidence": 0.9}]}

    review = build_review(recipe, matches, remix_path=Path("work/missing.mp4"), captions_path=Path("work/captions.srt"))

    assert review["status"] == "fail"
    assert any("remix" in failure for failure in review["failures"])


def test_review_fails_when_burned_caption_file_is_missing(tmp_path: Path):
    remix = tmp_path / "remix.mp4"
    captions = tmp_path / "captions.srt"
    contact_sheet = tmp_path / "contact-sheet.png"
    remix.write_bytes(b"not probed because monkeypatched")
    captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nCaption\n", encoding="utf-8")
    contact_sheet.write_bytes(b"image")
    recipe = {"duration_ms": 1000, "caption_burn_in": True, "segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}]}
    matches = {"matches": [{"id": "match-001", "segment_id": "seg-001", "status": "selected", "asset_id": "asset-001", "confidence": 0.9}]}

    review = build_review(
        recipe,
        matches,
        remix_path=remix,
        captions_path=captions,
        ass_path=tmp_path / "missing.ass",
        contact_sheet_path=contact_sheet,
    )

    assert review["status"] == "fail"
    assert any("captions.ass" in failure for failure in review["failures"])


def test_review_fails_when_contact_sheet_is_not_one_frame_per_segment(tmp_path: Path):
    contact_sheet = tmp_path / "contact-sheet.png"
    Image.new("RGB", (20, 20), "white").save(contact_sheet)
    recipe = {
        "duration_ms": 1000,
        "segments": [
            {"id": "seg-001", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "match_id": "match-002", "caption": "Pain"},
        ],
    }
    matches = {
        "matches": [
            {"id": "match-001", "segment_id": "seg-001", "status": "selected", "asset_id": "asset-001", "confidence": 0.9},
            {"id": "match-002", "segment_id": "seg-002", "status": "selected", "asset_id": "asset-002", "confidence": 0.9},
        ]
    }

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/missing.mp4"),
        captions_path=Path("work/missing.srt"),
        contact_sheet_path=contact_sheet,
    )

    assert review["status"] == "fail"
    assert any("contact sheet" in failure for failure in review["failures"])


def test_review_fails_when_contact_sheet_has_no_visual_detail(tmp_path: Path):
    contact_sheet = tmp_path / "contact-sheet.png"
    Image.new("RGB", (240, 120), "white").save(contact_sheet)
    recipe = {
        "duration_ms": 1000,
        "segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}],
    }
    matches = {"matches": [{"id": "match-001", "segment_id": "seg-001", "status": "selected", "asset_id": "asset-001", "confidence": 0.9}]}

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/missing.mp4"),
        captions_path=Path("work/missing.srt"),
        contact_sheet_path=contact_sheet,
    )

    assert review["status"] == "fail"
    assert any("visual detail" in failure for failure in review["failures"])


def test_review_warns_when_contact_sheet_has_platform_ui_risk(tmp_path: Path):
    contact_sheet = tmp_path / "contact-sheet.png"
    image = Image.new("RGB", (592, 1280), "#c8d8d0")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 250, 500, 760), fill="#557a95")
    for row in range(6):
        y = 1010 + row * 28
        for col in range(18):
            x = 24 + col * 30
            draw.rectangle((x, y, x + 18, y + 9), fill="white")
    image.save(contact_sheet)
    recipe = {
        "duration_ms": 1000,
        "segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}],
    }
    matches = {"matches": [{"id": "match-001", "segment_id": "seg-001", "status": "selected", "asset_id": "asset-001", "confidence": 0.9}]}

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/missing.mp4"),
        captions_path=Path("work/missing.srt"),
        contact_sheet_path=contact_sheet,
    )

    assert review["status"] == "fail"
    assert any("seg-001:" in warning and "platform UI" in warning for warning in review["warnings"])


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


def test_build_review_markdown_contains_plain_language_summary():
    markdown = build_review_markdown({"status": "pass", "outputs": {}, "warnings": [], "failures": []})

    assert "## Summary" in markdown
    assert "Usable rough cut" in markdown
    assert "Next action" in markdown


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


def test_build_review_html_contains_plain_language_summary():
    html = build_review_html(
        {"status": "warning", "outputs": {}, "warnings": ["low confidence"], "failures": []},
        {"segments": []},
        {"matches": []},
    )

    assert "<h2>Summary</h2>" in html
    assert "Needs review" in html


def test_write_review_html_creates_file(tmp_path: Path):
    output = tmp_path / "review.html"

    write_review_html({"status": "pass", "outputs": {}}, {"segments": []}, {"matches": []}, output)

    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_write_review_html_uses_relative_paths_for_local_outputs(tmp_path: Path):
    run_dir = tmp_path / "run"
    review = {
        "status": "pass",
        "outputs": {
            "remix": (run_dir / "remix.mp4").as_posix(),
            "contact_sheet": (run_dir / "contact-sheet.png").as_posix(),
            "voiceover": (run_dir / "voiceover.wav").as_posix(),
        },
        "warnings": [],
        "failures": [],
    }
    output = run_dir / "review.html"

    write_review_html(review, {"segments": []}, {"matches": []}, output)

    html = output.read_text(encoding="utf-8")
    assert 'src="remix.mp4"' in html
    assert 'src="contact-sheet.png"' in html
    assert tmp_path.as_posix() not in html
