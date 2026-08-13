from jianji_flow.review_summary import build_review_summary


def test_review_summary_maps_pass_to_usable_rough_cut():
    summary = build_review_summary({"status": "pass", "warnings": [], "failures": [], "low_confidence_segments": []})

    assert summary["decision"] == "Usable rough cut"
    assert "Watch captions" in summary["next_action"]


def test_review_summary_maps_warning_to_needs_review():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": ["seg-004 low confidence: 0.55"],
            "failures": [],
            "low_confidence_segments": ["seg-004"],
        }
    )

    assert summary["decision"] == "Needs review"
    assert "low confidence" in summary["reason"]


def test_review_summary_explains_same_source_warning_as_shell_risk():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": ["3 of 3 segments come from the same source video; the result may look like a voiceover shell instead of a true remix."],
            "failures": [],
            "low_confidence_segments": [],
        }
    )

    assert summary["decision"] == "Needs review"
    assert "voiceover shell" in summary["reason"]
    assert "compare it with the original" in summary["next_action"]


def test_review_summary_explains_platform_ui_warning_as_visual_cleanup():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": ["seg-003: possible platform UI or original subtitles in the lower safe area; captions may overlap."],
            "failures": [],
        }
    )

    assert summary["decision"] == "Needs review"
    assert "platform UI" in summary["reason"]
    assert "old subtitles" in summary["next_action"]


def test_review_summary_explains_filename_only_warning_as_visual_verification_risk():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": ["5 of 5 selected segments are filename only matches; watch the contact sheet."],
            "failures": [],
        }
    )

    assert summary["decision"] == "Needs review"
    assert "filename only" in summary["reason"]
    assert "contact sheet" in summary["next_action"]


def test_review_summary_explains_weak_story_support_as_story_review_risk():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": ["Story support is weak: 5 of 5 story roles rely only on filename evidence."],
            "failures": [],
        }
    )

    assert summary["decision"] == "Needs review"
    assert "Story support is weak" in summary["reason"]
    assert "product story" in summary["next_action"]


def test_review_summary_uses_story_support_specific_next_action():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": ["Story support is weak: 2 of 5 product story roles do not have visual evidence."],
            "failures": [],
            "story_support": {
                "status": "weak",
                "next_action": "Replace or manually verify evidence, cta clips.",
            },
        }
    )

    assert summary["decision"] == "Needs review"
    assert summary["next_action"] == "Replace or manually verify evidence, cta clips."


def test_review_summary_explains_talking_head_story_support_with_mode_roles():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": ["Story support is weak: 3 of 3 talking-head story roles do not have visual evidence."],
            "failures": [],
        }
    )

    assert summary["decision"] == "Needs review"
    assert "talking-head story" in summary["reason"]
    assert "topic, claim, explanation, evidence, and conclusion" in summary["next_action"]


def test_review_summary_prioritizes_source_visual_risk_over_filename_only_warning():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": [
                "5 of 5 selected segments are filename only matches; watch the contact sheet.",
                "seg-001 source frame 1: possible platform UI before rendering",
            ],
            "failures": [],
        }
    )

    assert summary["decision"] == "Needs review"
    assert "source frame" in summary["reason"]
    assert "platform UI" in summary["reason"]
    assert "old subtitles" in summary["next_action"]


def test_review_summary_prioritizes_same_source_risk_over_story_support_warning():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": [
                "Story support is weak: 5 of 5 story roles do not have visual evidence.",
                "5 of 5 segments come from the same source video; the result may look like a voiceover shell.",
            ],
            "failures": [],
        }
    )

    assert summary["decision"] == "Needs review"
    assert "same source video" in summary["reason"]
    assert "original" in summary["next_action"]


def test_review_summary_prioritizes_preflight_skipped_over_story_support_warning():
    summary = build_review_summary(
        {
            "status": "warning",
            "warnings": [
                "Story support is weak: 5 of 5 story roles do not have visual evidence.",
                "Source preflight skipped because ffprobe is unavailable.",
            ],
            "failures": [],
        }
    )

    assert summary["decision"] == "Needs review"
    assert "preflight skipped" in summary["reason"]
    assert "source diagnostics" in summary["next_action"]


def test_review_summary_maps_fail_to_do_not_use():
    summary = build_review_summary(
        {"status": "fail", "warnings": [], "failures": ["seg-002 missing asset"], "missing_segments": ["seg-002"]}
    )

    assert summary["decision"] == "Do not use yet"
    assert "missing" in summary["reason"].lower()
