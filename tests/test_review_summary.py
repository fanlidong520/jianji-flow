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


def test_review_summary_maps_fail_to_do_not_use():
    summary = build_review_summary(
        {"status": "fail", "warnings": [], "failures": ["seg-002 missing asset"], "missing_segments": ["seg-002"]}
    )

    assert summary["decision"] == "Do not use yet"
    assert "missing" in summary["reason"].lower()
