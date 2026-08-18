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
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
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

    assert review["status"] == "pass"
    assert review["failures"] == []
    assert review["warnings"] == []


def test_review_html_explains_when_media_was_not_generated(tmp_path):
    review = {
        "status": "fail",
        "failures": ["source frame failed preflight"],
        "warnings": [],
        "outputs": {
            "review_md": (tmp_path / "review.md").as_posix(),
            "source_diagnostics": (tmp_path / "source-diagnostics").as_posix(),
        },
    }
    recipe = {"segments": []}
    matches = {"matches": []}

    output_path = tmp_path / "review.html"
    write_review_html(review, recipe, matches, output_path)
    html = output_path.read_text(encoding="utf-8")

    assert "Do not use yet" in html
    assert "Output video was not generated" in html
    assert "Contact sheet was not generated" in html
    assert 'href="review.md"' in html
    assert 'src=""' not in html


def test_review_html_embeds_source_diagnostic_frames(tmp_path):
    diagnostics_dir = tmp_path / "source-diagnostics"
    diagnostics_dir.mkdir()
    Image.new("RGB", (12, 8), "red").save(diagnostics_dir / "seg-001-01.png")
    review = {
        "status": "fail",
        "failures": ["source frame failed preflight"],
        "warnings": [],
        "outputs": {"source_diagnostics": diagnostics_dir.as_posix()},
    }

    output_path = tmp_path / "review.html"
    write_review_html(review, {"segments": []}, {"matches": []}, output_path)
    html = output_path.read_text(encoding="utf-8")

    assert "Source diagnostics" in html
    assert 'src="source-diagnostics/seg-001-01.png"' in html


def test_review_warns_when_most_segments_come_from_same_source():
    recipe = {
        "segments": [
            {"id": "seg-001", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "match_id": "match-002", "caption": "Pain"},
            {"id": "seg-003", "match_id": "match-003", "caption": "Feature"},
        ]
    }
    matches = {
        "matches": [
            {"id": "match-001", "segment_id": "seg-001", "status": "selected", "asset_id": "asset-001", "source_path": "assets/mother.mp4", "confidence": 0.9},
            {"id": "match-002", "segment_id": "seg-002", "status": "selected", "asset_id": "asset-002", "source_path": "assets/mother.mp4", "confidence": 0.9},
            {"id": "match-003", "segment_id": "seg-003", "status": "selected", "asset_id": "asset-003", "source_path": "assets/mother.mp4", "confidence": 0.9},
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
    assert any("same source video" in warning for warning in review["warnings"])


def test_review_exposes_edit_diversity_in_review_outputs():
    recipe = {
        "segments": [
            {"id": "seg-001", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "match_id": "match-002", "caption": "Pain"},
            {"id": "seg-003", "match_id": "match-003", "caption": "Feature"},
            {"id": "seg-004", "match_id": "match-004", "caption": "Proof"},
        ]
    }
    matches = {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "asset_id": f"asset-{index:03d}",
                "source_path": "assets/mother.mp4",
                "source_start_ms": (index - 1) * 1000,
                "source_end_ms": index * 1000,
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
            }
            for index in range(1, 5)
        ]
    }

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/remix.mp4"),
        captions_path=Path("work/captions.srt"),
        check_artifacts=False,
    )
    markdown = build_review_markdown(review, recipe, matches)
    html = build_review_html(review, recipe, matches)

    assert review["edit_diversity"]["status"] == "warning"
    assert review["edit_diversity"]["distinct_source_video_count"] == 1
    assert "## Edit diversity" in markdown
    assert "- distinct_source_video_count: 1" in markdown
    assert "Edit diversity" in html
    assert "voiceover shell" in html


def test_review_warns_when_selected_segments_are_filename_only_matches():
    recipe = {
        "segments": [
            {"id": "seg-001", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "match_id": "match-002", "caption": "Pain"},
            {"id": "seg-003", "match_id": "match-003", "caption": "Feature"},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "source_path": "assets/01-hook.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:hook"],
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "status": "selected",
                "asset_id": "asset-002",
                "source_path": "assets/02-pain.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:pain"],
            },
            {
                "id": "match-003",
                "segment_id": "seg-003",
                "status": "selected",
                "asset_id": "asset-003",
                "source_path": "assets/03-feature.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
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
    assert any("filename only" in warning for warning in review["warnings"])
    assert review["story_support"]["status"] == "weak"
    assert review["story_support"]["roles"] == ["hook", "pain", "feature"]


def test_review_treats_source_window_as_non_visual_evidence():
    roles = ("hook", "pain", "feature", "evidence", "cta")
    recipe = {
        "mode": "product",
        "segments": [
            {"id": f"seg-{index:03d}", "role": role, "match_id": f"match-{index:03d}", "caption": role}
            for index, role in enumerate(roles, start=1)
        ],
    }
    matches = {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "asset_id": f"asset-{index:03d}",
                "source_path": f"assets/{index:02d}.mp4",
                "confidence": 0.92,
                "evidence": [f"filename-role:{role}", "source-window:1000-2000"],
            }
            for index, role in enumerate(roles, start=1)
        ]
    }

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/remix.mp4"),
        captions_path=Path("work/captions.srt"),
        check_artifacts=False,
    )

    assert any("filename only" in warning for warning in review["warnings"])
    assert review["story_support"]["filename_only_roles"] == list(roles)
    assert review["story_support"]["visual_evidence_roles"] == []
    assert review["story_support"]["weak_evidence_roles"] == list(roles)


def test_review_treats_source_preflight_clean_as_non_story_evidence():
    roles = ("hook", "pain", "feature", "evidence", "cta")
    recipe = {
        "mode": "product",
        "segments": [
            {"id": f"seg-{index:03d}", "role": role, "match_id": f"match-{index:03d}", "caption": role}
            for index, role in enumerate(roles, start=1)
        ],
    }
    matches = {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "asset_id": f"asset-{index:03d}",
                "source_path": f"assets/{index:02d}.mp4",
                "confidence": 0.92,
                "evidence": [f"filename-role:{role}", "source-preflight:clean"],
            }
            for index, role in enumerate(roles, start=1)
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
    assert review["story_support"]["visual_evidence_roles"] == []
    assert review["story_support"]["weak_evidence_roles"] == list(roles)


def test_review_story_support_passes_with_non_filename_story_evidence():
    recipe = {
        "mode": "product",
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "role": "pain", "match_id": "match-002", "caption": "Pain"},
            {"id": "seg-003", "role": "feature", "match_id": "match-003", "caption": "Feature"},
            {"id": "seg-004", "role": "evidence", "match_id": "match-004", "caption": "Evidence"},
            {"id": "seg-005", "role": "cta", "match_id": "match-005", "caption": "CTA"},
        ],
    }
    matches = {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "asset_id": f"asset-{index:03d}",
                "source_path": f"assets/{index:02d}.mp4",
                "confidence": 0.88,
                "evidence": ["filename-role:hook", "visual-frame:matches-caption"],
            }
            for index in range(1, 6)
        ]
    }

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/remix.mp4"),
        captions_path=Path("work/captions.srt"),
        check_artifacts=False,
    )

    assert review["status"] == "pass"
    assert review["story_support"]["status"] == "pass"
    assert review["story_support"]["roles"] == ["hook", "pain", "feature", "evidence", "cta"]


def test_review_story_support_ignores_non_visual_metadata_evidence():
    recipe = {
        "mode": "product",
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "role": "pain", "match_id": "match-002", "caption": "Pain"},
            {"id": "seg-003", "role": "feature", "match_id": "match-003", "caption": "Feature"},
        ],
    }
    matches = {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "asset_id": f"asset-{index:03d}",
                "source_path": f"assets/{index:02d}.mp4",
                "confidence": 0.8,
                "evidence": ["duration-fit:yes"],
            }
            for index in range(1, 4)
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
    assert review["story_support"]["status"] == "weak"
    assert review["story_support"]["visual_evidence_roles"] == []


def test_review_fails_when_no_selected_clips_support_story():
    review = build_review(
        {"mode": "product", "segments": []},
        {"matches": []},
        remix_path=Path("work/remix.mp4"),
        captions_path=Path("work/captions.srt"),
        check_artifacts=False,
    )

    assert review["status"] == "fail"
    assert review["story_support"]["status"] == "fail"
    assert any("No selected clips support the story" in failure for failure in review["failures"])


def test_review_warns_when_story_roles_have_no_visual_evidence():
    recipe = {
        "mode": "product",
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "role": "pain", "match_id": "match-002", "caption": "Pain"},
            {"id": "seg-003", "role": "feature", "match_id": "match-003", "caption": "Feature"},
        ],
    }
    matches = {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "asset_id": f"asset-{index:03d}",
                "source_path": f"assets/{index:02d}.mp4",
                "confidence": 0.8,
                "evidence": [],
            }
            for index in range(1, 4)
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
    assert review["story_support"]["status"] == "weak"
    assert any("Story support is weak" in warning for warning in review["warnings"])


def test_review_warns_when_adjacent_segments_use_same_source():
    recipe = {
        "mode": "product",
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature"},
            {"id": "seg-002", "role": "evidence", "match_id": "match-002", "caption": "Evidence"},
        ],
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-demo",
                "source_path": "assets/demo.mp4",
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "status": "selected",
                "asset_id": "asset-demo",
                "source_path": "assets/demo.mp4",
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
            },
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
    assert any("Adjacent segments seg-001 and seg-002 use the same source video" in warning for warning in review["warnings"])


def test_review_story_support_warning_uses_talking_head_language():
    recipe = {
        "mode": "talking-head",
        "segments": [
            {"id": "seg-001", "role": "topic", "match_id": "match-001", "caption": "Topic"},
            {"id": "seg-002", "role": "claim", "match_id": "match-002", "caption": "Claim"},
            {"id": "seg-003", "role": "explanation", "match_id": "match-003", "caption": "Explanation"},
        ],
    }
    matches = {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "asset_id": f"asset-{index:03d}",
                "source_path": f"assets/{index:02d}.mp4",
                "confidence": 0.8,
                "evidence": [],
            }
            for index in range(1, 4)
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
    assert "talking-head story" in review["story_support"]["warning"]


def test_review_warns_when_short_story_has_no_visual_evidence():
    recipe = {
        "mode": "product",
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "role": "pain", "match_id": "match-002", "caption": "Pain"},
        ],
    }
    matches = {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "asset_id": f"asset-{index:03d}",
                "source_path": f"assets/{index:02d}.mp4",
                "confidence": 0.8,
                "evidence": [],
            }
            for index in range(1, 3)
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
    assert review["story_support"]["status"] == "weak"


def test_review_warns_when_most_story_roles_have_no_visual_evidence():
    recipe = {
        "mode": "product",
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "role": "pain", "match_id": "match-002", "caption": "Pain"},
            {"id": "seg-003", "role": "feature", "match_id": "match-003", "caption": "Feature"},
            {"id": "seg-004", "role": "evidence", "match_id": "match-004", "caption": "Evidence"},
            {"id": "seg-005", "role": "cta", "match_id": "match-005", "caption": "CTA"},
        ],
    }
    matches = {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "asset_id": f"asset-{index:03d}",
                "source_path": f"assets/{index:02d}.mp4",
                "confidence": 0.8,
                "evidence": ["visual-frame:matches-caption"] if index in (1, 2) else [],
            }
            for index in range(1, 6)
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
    assert review["story_support"]["status"] == "weak"
    assert review["story_support"]["weak_evidence_roles"] == ["feature", "evidence", "cta"]
    assert "Replace or manually verify feature, evidence, cta clips" in review["story_support"]["next_action"]


def test_review_fails_when_rendered_video_is_missing():
    recipe = {"duration_ms": 1000, "segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}]}
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
            }
        ]
    }

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
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
            }
        ]
    }

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
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
            }
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
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
            }
        ]
    }

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/missing.mp4"),
        captions_path=Path("work/missing.srt"),
        contact_sheet_path=contact_sheet,
        check_artifacts=False,
    )

    diagnosis_review = build_review(
        recipe,
        matches,
        remix_path=Path("work/missing.mp4"),
        captions_path=Path("work/missing.srt"),
        contact_sheet_path=contact_sheet,
    )

    assert diagnosis_review["status"] == "fail"
    assert review["status"] == "pass"


def test_review_artifact_review_warns_when_contact_sheet_has_platform_ui_risk(tmp_path: Path, monkeypatch):
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
    remix = tmp_path / "remix.mp4"
    captions = tmp_path / "captions.srt"
    remix.write_bytes(b"probe is monkeypatched")
    captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nHook\n", encoding="utf-8")

    class ProbeInfo:
        has_audio = True
        duration_ms = 1000

    monkeypatch.setattr("jianji_flow.review.run_ffprobe", lambda path: ProbeInfo())
    recipe = {
        "duration_ms": 1000,
        "segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}],
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
            }
        ]
    }

    review = build_review(
        recipe,
        matches,
        remix_path=remix,
        captions_path=captions,
        contact_sheet_path=contact_sheet,
    )

    assert review["status"] == "warning"
    assert any("seg-001:" in warning and "platform UI" in warning for warning in review["warnings"])


def test_review_fails_when_contact_sheet_has_severe_platform_ui_risk(tmp_path: Path):
    contact_sheet = tmp_path / "contact-sheet.png"
    image = Image.new("RGB", (592, 1280), "#c8d8d0")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 250, 500, 760), fill="#557a95")
    for row in range(18):
        y = 910 + row * 18
        for col in range(24):
            x = 12 + col * 24
            draw.rectangle((x, y, x + 16, y + 8), fill="white")
    image.save(contact_sheet)
    recipe = {
        "duration_ms": 1000,
        "segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}],
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "confidence": 0.9,
                "evidence": ["visual-frame:matches-caption"],
            }
        ]
    }

    review = build_review(
        recipe,
        matches,
        remix_path=Path("work/missing.mp4"),
        captions_path=Path("work/missing.srt"),
        contact_sheet_path=contact_sheet,
        check_artifacts=False,
    )

    assert review["status"] == "pass"


def test_review_artifact_review_fails_when_contact_sheet_has_severe_platform_ui_risk(tmp_path: Path, monkeypatch):
    contact_sheet = tmp_path / "contact-sheet.png"
    image = Image.new("RGB", (592, 1280), "#c8d8d0")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 250, 500, 760), fill="#557a95")
    for row in range(18):
        y = 910 + row * 18
        for col in range(24):
            x = 12 + col * 24
            draw.rectangle((x, y, x + 16, y + 8), fill="white")
    image.save(contact_sheet)
    remix = tmp_path / "remix.mp4"
    captions = tmp_path / "captions.srt"
    remix.write_bytes(b"probe is monkeypatched")
    captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nHook\n", encoding="utf-8")

    class ProbeInfo:
        has_audio = True
        duration_ms = 1000

    monkeypatch.setattr("jianji_flow.review.run_ffprobe", lambda path: ProbeInfo())
    recipe = {
        "duration_ms": 1000,
        "segments": [{"id": "seg-001", "match_id": "match-001", "caption": "Hook"}],
    }
    matches = {"matches": [{"id": "match-001", "segment_id": "seg-001", "status": "selected", "asset_id": "asset-001", "confidence": 0.9}]}

    review = build_review(
        recipe,
        matches,
        remix_path=remix,
        captions_path=captions,
        contact_sheet_path=contact_sheet,
    )

    assert review["status"] == "fail"
    assert any("severe platform UI" in failure for failure in review["failures"])


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


def test_build_review_markdown_contains_story_support_section():
    markdown = build_review_markdown(
        {
            "status": "warning",
            "warnings": [],
            "failures": [],
            "outputs": {},
            "story_support": {
                "status": "weak",
                "roles": ["hook", "pain", "feature", "evidence", "cta"],
                "filename_only_roles": ["hook", "pain"],
                "visual_evidence_roles": ["feature"],
                "weak_evidence_roles": ["hook", "pain"],
                "next_action": "Replace or manually verify hook, pain clips.",
            },
        }
    )

    assert "## Story support" in markdown
    assert "- status: weak" in markdown
    assert "- filename_only_roles: hook, pain" in markdown
    assert "- next_action: Replace or manually verify hook, pain clips." in markdown


def test_build_review_markdown_contains_storyboard_rows():
    review = {
        "status": "warning",
        "warnings": ["seg-001 low confidence"],
        "failures": [],
        "outputs": {},
    }
    recipe = {
        "segments": [
            {
                "id": "seg-001",
                "role": "hook",
                "match_id": "match-001",
                "caption": "Open with the dust problem",
                "start_ms": 0,
                "end_ms": 1200,
            }
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "source_path": "assets/01-hook.mp4",
                "source_start_ms": 200,
                "source_end_ms": 1400,
                "confidence": 0.55,
                "evidence": ["filename-role:hook", "sequence-diversity:avoids-adjacent-source"],
            }
        ]
    }

    markdown = build_review_markdown(review, recipe, matches)

    assert "## Storyboard" in markdown
    assert "seg-001" in markdown
    assert "hook" in markdown
    assert "Open with the dust problem" in markdown
    assert "assets/01-hook.mp4" in markdown
    assert "200-1400ms" in markdown
    assert "filename-role:hook" in markdown
    assert "low confidence" in markdown


def test_build_review_contains_final_shot_plan():
    review = {
        "status": "warning",
        "warnings": [],
        "failures": [],
        "outputs": {},
        "shot_plan": {
            "status": "pass",
            "total_shots": 3,
            "segments": [
                {
                    "segment_id": "seg-001",
                    "shot_count": 2,
                    "status": "detected",
                    "boundaries_ms": [1200, 1950, 2800],
                }
            ],
        },
    }

    markdown = build_review_markdown(review, {"segments": []}, {"matches": []})
    html = build_review_html(review, {"segments": []}, {"matches": []})

    assert "## Shot plan" in markdown
    assert "1200ms, 1950ms, 2800ms" in markdown
    assert "Shot plan" in html
    assert "Total shots:" in html
    assert "1200ms, 1950ms, 2800ms" in html


def test_build_review_contains_shot_contact_sheet_output():
    review = {
        "status": "warning",
        "warnings": [],
        "failures": [],
        "outputs": {"shot_contact_sheet": "shot-contact-sheet.png"},
    }

    markdown = build_review_markdown(review, {"segments": []}, {"matches": []})
    html = build_review_html(review, {"segments": []}, {"matches": []})

    assert "## Shot timeline" in markdown
    assert "shot-contact-sheet.png" in markdown
    assert "Shot Timeline" in html
    assert 'src="shot-contact-sheet.png"' in html


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
            "reference_comparison": "work/reference-comparison.png",
            "voiceover": "work/voiceover.wav",
            "candidate_review": "work/candidate-review.html",
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
    assert "work/reference-comparison.png" in html
    assert "Reference vs Remix" in html
    assert "work/voiceover.wav" in html
    assert "candidate-review.html" in html
    assert "家里难刷角落" in html
    assert "filename-role:hook" in html


def test_build_review_html_contains_story_support_status():
    review = {
        "status": "warning",
        "outputs": {},
        "warnings": [],
        "failures": [],
        "story_support": {
            "status": "weak",
            "roles": ["hook", "pain"],
            "filename_only_roles": ["hook"],
            "visual_evidence_roles": [],
            "weak_evidence_roles": ["hook"],
            "next_action": "Replace or manually verify hook clips.",
        },
    }

    html = build_review_html(review, {"segments": []}, {"matches": []})

    assert "Story support" in html
    assert "weak" in html
    assert "filename_only_roles" in html
    assert "Replace or manually verify hook clips." in html


def test_build_review_html_contains_storyboard_rows():
    review = {
        "status": "warning",
        "outputs": {},
        "warnings": ["Adjacent segments seg-001 and seg-002 use the same source video"],
        "failures": [],
    }
    recipe = {
        "segments": [
            {
                "id": "seg-001",
                "role": "feature",
                "match_id": "match-001",
                "caption": "Show the product detail",
                "start_ms": 1000,
                "end_ms": 2600,
            }
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "source_path": "assets/03-feature.mp4",
                "source_start_ms": 3000,
                "source_end_ms": 4600,
                "confidence": 0.92,
                "evidence": ["filename-role:feature", "source-window:3000-4600"],
            }
        ]
    }

    html = build_review_html(review, recipe, matches)

    assert "Storyboard" in html
    assert "seg-001" in html
    assert "feature" in html
    assert "Show the product detail" in html
    assert "assets/03-feature.mp4" in html
    assert "3000-4600ms" in html
    assert "source-window:3000-4600" in html
    assert "same source video" in html


def test_build_review_markdown_contains_change_report():
    review = {
        "status": "warning",
        "warnings": [],
        "failures": [],
        "outputs": {},
        "change_report": {
            "changed_segments": [
                {
                    "segment_id": "seg-003",
                    "role": "feature",
                    "caption": "Show the product detail",
                    "before_asset": "assets/03-feature.mp4",
                    "before_range": "0-1600ms",
                    "before_frame": "change-diagnostics/seg-003-before.png",
                    "after_asset": "assets/05-cta.mp4",
                    "after_range": "200-1800ms",
                    "after_frame": "change-diagnostics/seg-003-after.png",
                    "visual_difference": 42.5,
                    "reason": "override:seg-003",
                }
            ],
            "unchanged_segments": ["seg-001", "seg-002"],
            "unaccounted_segments": ["seg-004"],
        },
    }

    markdown = build_review_markdown(review, {"segments": []}, {"matches": []})

    assert "## Change report" in markdown
    assert "Picture change only means sampled frames differ; it does not prove the new shot fits the script." in markdown
    assert "| Segment | Role | Caption | Before | After | Picture change | Sampling note | Reason |" in markdown
    assert "seg-003" in markdown
    assert "assets/03-feature.mp4 @ 0-1600ms; frame: change-diagnostics/seg-003-before.png" in markdown
    assert "assets/05-cta.mp4 @ 200-1800ms; frame: change-diagnostics/seg-003-after.png" in markdown
    assert "42.5" in markdown
    assert "override:seg-003" in markdown
    assert "Unchanged segments: seg-001, seg-002" in markdown
    assert "Unaccounted segments: seg-004" in markdown


def test_build_review_html_contains_change_report():
    review = {
        "status": "warning",
        "outputs": {},
        "warnings": [],
        "failures": [],
        "change_report": {
            "changed_segments": [
                {
                    "segment_id": "seg-003",
                    "role": "feature",
                    "caption": "Show the product detail",
                    "before_asset": "assets/03-feature.mp4",
                    "before_range": "0-1600ms",
                    "before_frame": "change-diagnostics/seg-003-before.png",
                    "after_asset": "assets/05-cta.mp4",
                    "after_range": "200-1800ms",
                    "after_frame": "change-diagnostics/seg-003-after.png",
                    "visual_difference": 42.5,
                    "visual_difference_warning": "review this sampled frame manually",
                    "reason": "override:seg-003",
                }
            ],
            "unchanged_segments": ["seg-001", "seg-002"],
            "unaccounted_segments": ["seg-004"],
        },
    }

    html = build_review_html(review, {"segments": []}, {"matches": []})

    assert "Change report" in html
    assert "Picture change only means sampled frames differ" in html
    assert "seg-003" in html
    assert "assets/03-feature.mp4 @ 0-1600ms" in html
    assert "assets/05-cta.mp4 @ 200-1800ms" in html
    assert 'src="change-diagnostics/seg-003-before.png"' in html
    assert 'src="change-diagnostics/seg-003-after.png"' in html
    assert "42.5" in html
    assert "review this sampled frame manually" in html
    assert "override:seg-003" in html
    assert "Unchanged segments: seg-001, seg-002" in html
    assert "Unaccounted segments: seg-004" in html


def test_build_review_omits_change_report_when_not_present():
    markdown = build_review_markdown({"status": "warning", "warnings": [], "failures": [], "outputs": {}})
    html = build_review_html({"status": "warning", "outputs": {}, "warnings": [], "failures": []}, {"segments": []}, {"matches": []})

    assert "Change report" not in markdown
    assert "Change report" not in html


def test_build_review_markdown_contains_visual_selection_evidence(tmp_path: Path):
    review = {
        "status": "pass",
        "failures": [],
        "warnings": [],
        "outputs": {},
        "visual_selection": {
            "candidate_sheet": "visual-candidate-sheet.png",
            "selections": [
                {
                    "segment_id": "seg-001",
                    "candidate_id": "seg-001-candidate-01",
                    "reviewer": "codex-vision",
                    "reason": "画面展示了使用过程。",
                    "frames": ["visual-candidates/seg-001-candidate-01-02.png"],
                }
            ],
        },
    }
    markdown = build_review_markdown(review)

    assert "## Visual selection" in markdown
    assert "Codex visual review" in markdown
    assert "seg-001-candidate-01" in markdown
    assert "not semantic proof" in markdown


def test_build_review_html_contains_visual_selection_evidence(tmp_path: Path):
    review = {
        "status": "pass",
        "failures": [],
        "warnings": [],
        "outputs": {},
        "visual_selection": {
            "candidate_sheet": "visual-candidate-sheet.png",
            "selections": [
                {
                    "segment_id": "seg-001",
                    "candidate_id": "seg-001-candidate-01",
                    "reviewer": "codex-vision",
                    "reason": "画面展示了使用过程。",
                    "frames": ["visual-candidates/seg-001-candidate-01-02.png"],
                }
            ],
        },
    }
    html = build_review_html(review, {"segments": []}, {"matches": []})

    assert "Visual selection" in html
    assert "Codex visual review" in html
    assert "seg-001-candidate-01" in html
    assert "not semantic proof" in html


def test_build_review_visual_selection_shows_final_retimed_frames():
    review = {
        "status": "pass",
        "failures": [],
        "warnings": [],
        "outputs": {},
        "visual_selection": {
            "selections": [
                {
                    "segment_id": "seg-001",
                    "candidate_id": "seg-001-candidate-01",
                    "reviewer": "codex-vision",
                    "reason": "supports the segment",
                    "frames": ["candidate-frame.png"],
                    "final_source_range": "1000-2000ms",
                    "final_frames": ["final-frame.png"],
                }
            ]
        },
    }

    markdown = build_review_markdown(review)
    html = build_review_html(review, {"segments": []}, {"matches": []})

    assert "Final selected frames" in markdown
    assert "1000-2000ms" in markdown
    assert "Final selected frames" in html
    assert 'src="final-frame.png"' in html


def test_build_review_html_contains_plain_language_summary():
    html = build_review_html(
        {"status": "warning", "outputs": {}, "warnings": ["low confidence"], "failures": []},
        {"segments": []},
        {"matches": []},
    )

    assert "<h2>Summary</h2>" in html
    assert "Needs review" in html


def test_build_review_html_contains_nontechnical_verdict_panel_for_warning():
    html = build_review_html(
        {
            "status": "warning",
            "outputs": {
                "remix": "remix.mp4",
                "contact_sheet": "contact-sheet.png",
                "reference_comparison": "reference-comparison.png",
            },
            "warnings": [
                "5 of 5 segments come from the same source video; "
                "the result may look like a voiceover shell instead of a true remix."
            ],
            "failures": [],
            "story_support": {
                "status": "weak",
                "roles": ["hook", "pain", "feature", "evidence", "cta"],
                "filename_only_roles": [],
                "visual_evidence_roles": ["hook"],
                "weak_evidence_roles": ["pain", "feature", "evidence", "cta"],
                "next_action": "Replace or manually verify pain, feature, evidence, cta clips.",
            },
        },
        {"segments": []},
        {"matches": []},
    )

    assert "能不能用" in html
    assert "只能当待确认粗剪" in html
    assert "先看哪里" in html
    assert "先看 Reference vs Remix" in html
    assert "可能只是换配音或同源复用" in html


def test_write_review_html_creates_file(tmp_path: Path):
    output = tmp_path / "review.html"

    write_review_html({"status": "pass", "outputs": {}}, {"segments": []}, {"matches": []}, output)

    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_write_review_html_relativizes_final_visual_frames(tmp_path: Path):
    frame = tmp_path / "visual-selection-evidence" / "final-frames" / "seg-001-01.png"
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b"frame")
    output = tmp_path / "review.html"
    review = {
        "status": "pass",
        "outputs": {},
        "visual_selection": {
            "selections": [
                {
                    "segment_id": "seg-001",
                    "final_frames": [frame.as_posix()],
                    "final_source_range": "0-1000ms",
                }
            ]
        },
    }

    write_review_html(review, {"segments": []}, {"matches": []}, output)

    html = output.read_text(encoding="utf-8")
    assert 'src="visual-selection-evidence/final-frames/seg-001-01.png"' in html
    assert str(frame) not in html


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
