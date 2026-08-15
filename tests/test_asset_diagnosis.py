from pathlib import Path

from jianji_flow.asset_diagnosis import diagnose_product_assets, format_asset_diagnosis
from jianji_flow.planner import build_segment_plan


def _asset(name: str, duration_ms: int = 10_000) -> dict:
    return {"asset_id": name, "path": Path(name).as_posix(), "duration_ms": duration_ms}


def test_product_asset_diagnosis_marks_well_named_roles_ready():
    segments = build_segment_plan("product", 10_000, None)
    assets = [_asset(f"01-{role}.mp4") for role in ("hook", "pain", "feature", "evidence", "cta")]

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "pass"
    assert all(item["status"] == "ready" for item in report["roles"].values())


def test_product_asset_diagnosis_marks_missing_role_as_fail():
    segments = build_segment_plan("product", 10_000, None)
    assets = [_asset("01-hook.mp4"), _asset("02-pain.mp4"), _asset("03-feature.mp4")]

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "fail"
    assert report["roles"]["evidence"]["status"] == "missing"
    assert any("Missing evidence clip" in item for item in report["actions"])


def test_product_asset_diagnosis_marks_short_role_as_weak():
    segments = build_segment_plan("product", 10_000, None)
    assets = [
        _asset("01-hook.mp4"),
        _asset("02-pain.mp4"),
        _asset("03-feature.mp4"),
        _asset("04-evidence.mp4", duration_ms=100),
        _asset("05-cta.mp4"),
    ]

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "warning"
    assert report["roles"]["evidence"]["status"] == "weak"
    assert "too short" in " ".join(report["actions"])


def test_product_asset_diagnosis_marks_chinese_role_filenames_ready():
    segments = build_segment_plan("product", 10_000, None)
    assets = [_asset(name) for name in ("开头.mp4", "痛点.mp4", "产品卖点.mp4", "使用对比.mp4", "结尾下单.mp4")]

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "pass"


def test_product_asset_diagnosis_warns_when_different_names_share_exact_media():
    segments = build_segment_plan("product", 10_000, None)
    assets = [_asset(f"01-{role}.mp4") for role in ("hook", "pain", "feature", "evidence", "cta")]
    assets[1]["sha256"] = "same-media"
    assets[2]["sha256"] = "same-media"

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "warning"
    assert report["duplicate_groups"] == [
        {"sha256": "same-media", "paths": ["01-pain.mp4", "01-feature.mp4"]}
    ]
    assert any("duplicate media" in action.lower() for action in report["actions"])
    text = format_asset_diagnosis(report)
    assert "DUPLICATE MEDIA" in text
    assert "different filenames do not prove independent footage" in text


def test_format_asset_diagnosis_reports_visual_similarity_without_claiming_same_source():
    report = {
        "status": "warning",
        "roles": {},
        "actions": [],
        "source_diversity": {
            "status": "warning",
            "similar_groups": [
                {"paths": ["assets/source.mp4", "assets/reencoded.mp4"], "score": 1.5}
            ],
            "warnings": [],
            "diagnostics_dir": "work/source-diversity-diagnostics",
        },
    }

    text = format_asset_diagnosis(report)

    assert "SIMILAR MEDIA" in text
    assert "1.5" in text
    assert "may be a re-encoded or cropped copy" in text
    assert "does not prove the same mother video" in text


def test_format_asset_diagnosis_reports_partial_overlap_coverage():
    report = {
        "status": "warning",
        "roles": {},
        "actions": [],
        "source_diversity": {
            "status": "warning",
            "similar_groups": [
                {
                    "paths": ["assets/mother.mp4", "assets/cut.mp4"],
                    "score": 3.154,
                    "coverage": 0.667,
                    "match_mode": "partial-overlap",
                }
            ],
            "warnings": [],
            "diagnostics_dir": "work/source-diversity-diagnostics",
        },
    }

    text = format_asset_diagnosis(report)

    assert "partial-overlap" in text
    assert "0.667" in text


def test_product_asset_diagnosis_does_not_reuse_one_clip_for_all_roles():
    segments = build_segment_plan("product", 10_000, None)
    assets = [_asset("before-after-demo-product-buy.mp4", duration_ms=30_000)]

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "fail"
    assert report["roles"]["evidence"]["status"] == "ready"
    assert report["roles"]["cta"]["status"] == "missing"


def test_product_asset_diagnosis_treats_bad_durations_as_weak():
    segments = build_segment_plan("product", 10_000, None)
    assets = [
        _asset("01-hook.mp4"),
        _asset("02-pain.mp4"),
        _asset("03-feature.mp4"),
        {"asset_id": "bad", "path": "04-evidence.mp4", "duration_ms": "not-a-number"},
        _asset("05-cta.mp4"),
    ]

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "warning"
    assert report["roles"]["evidence"]["status"] == "weak"


def test_product_asset_diagnosis_handles_empty_segment_plan():
    report = diagnose_product_assets([_asset("01-hook.mp4")], [])

    assert report["status"] == "fail"
    assert any("segment plan" in item.lower() for item in report["actions"])


def test_format_asset_diagnosis_ends_with_decision():
    segments = build_segment_plan("product", 10_000, None)
    report = diagnose_product_assets(
        [_asset(f"01-{role}.mp4") for role in ("hook", "pain", "feature", "evidence", "cta")],
        segments,
    )

    text = format_asset_diagnosis(report)

    assert "Material diagnosis" in text
    assert "hook / 开头" in text
    assert "Filename and duration screening only" in text
    assert "CANDIDATE" in text
    assert "READY" not in text
    assert "not visual proof" in text
    assert text.strip().endswith("Can run quick draft; inspect contact-sheet before publishing")


def test_format_asset_diagnosis_uses_plain_chinese_next_actions():
    segments = build_segment_plan("product", 10_000, None)
    report = diagnose_product_assets([_asset("01-hook.mp4")], segments)

    text = format_asset_diagnosis(report)

    assert "下一步" in text
    assert "缺少痛点素材" in text
    assert "02-pain" in text
    assert "Missing pain clip" not in text


def test_format_asset_diagnosis_does_not_call_opaque_files_missing_after_visual_selection():
    segments = build_segment_plan("product", 10_000, None)
    report = diagnose_product_assets([_asset(f"IMG_{index:03d}.mp4") for index in range(1, 6)], segments)

    text = format_asset_diagnosis(report, visual_selection_supplied=True)

    assert "VISUAL REVIEW SUPPLIED" in text
    assert "MISSING" not in text
    assert "filename screening is not used as the final role decision" in text
