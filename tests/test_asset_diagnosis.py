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
    assert "Filename and duration screening only" in text
    assert text.strip().endswith("Ready to run quick draft")
