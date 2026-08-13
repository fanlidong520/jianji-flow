from dataclasses import dataclass
from pathlib import Path

import jianji_flow.matcher as matcher_module
from jianji_flow.contracts import validate_matches, validate_recipe
from jianji_flow.matcher import build_recipe, match_segments, retime_recipe_and_matches


@dataclass(frozen=True)
class FakeAsset:
    asset_id: str
    path: Path
    duration_ms: int
    width: int = 1080
    height: int = 1920
    fps: float = 30.0
    has_audio: bool = True


def _segments():
    return [
        {"id": "seg-001", "role": "hook", "start_ms": 0, "end_ms": 1000, "caption": "Hook"},
        {"id": "seg-002", "role": "feature", "start_ms": 1000, "end_ms": 2500, "caption": "Feature"},
    ]


def test_match_segments_marks_missing_when_assets_empty():
    result = match_segments(_segments(), [])

    validate_matches(result)
    assert [match["status"] for match in result["matches"]] == ["missing", "missing"]
    assert all(match["confidence"] == 0 for match in result["matches"])
    assert all("missing_reason" in match for match in result["matches"])


def test_match_segments_prefers_role_in_filename():
    assets = [
        FakeAsset("asset-other", Path("assets/other.mp4"), 5000),
        FakeAsset("asset-hook", Path("assets/product-hook.mp4"), 5000),
    ]

    result = match_segments([_segments()[0]], assets)

    validate_matches(result)
    match = result["matches"][0]
    assert match["status"] == "selected"
    assert match["asset_id"] == "asset-hook"
    assert match["source_path"] == "assets/product-hook.mp4"
    assert match["segment_id"] == "seg-001"
    assert any("filename-role" in item for item in match["evidence"])


def test_match_segments_prefers_non_adjacent_source_for_repeated_role():
    segments = [
        {"id": "seg-001", "role": "feature", "start_ms": 0, "end_ms": 1000, "caption": "Feature A"},
        {"id": "seg-002", "role": "feature", "start_ms": 1000, "end_ms": 2000, "caption": "Feature B"},
    ]
    assets = [
        FakeAsset("asset-feature-a", Path("assets/feature-a.mp4"), 5000),
        FakeAsset("asset-feature-b", Path("assets/feature-b.mp4"), 5000),
    ]

    result = match_segments(segments, assets)

    validate_matches(result)
    assert [match["asset_id"] for match in result["matches"]] == ["asset-feature-a", "asset-feature-b"]
    assert "sequence-diversity:avoids-adjacent-source" in result["matches"][1]["evidence"]


def test_match_segments_uses_nonzero_source_window_for_long_assets():
    segment = {"id": "seg-003", "role": "feature", "start_ms": 4000, "end_ms": 6000, "caption": "Feature"}
    assets = [FakeAsset("asset-feature", Path("assets/feature.mp4"), 10_000)]

    result = match_segments([segment], assets)

    validate_matches(result)
    match = result["matches"][0]
    assert match["source_start_ms"] > 0
    assert match["source_end_ms"] - match["source_start_ms"] == 2000
    assert any("source-window:" in item for item in match["evidence"])


def test_match_segments_uses_window_scorer_to_choose_source_window():
    segment = {"id": "seg-003", "role": "feature", "start_ms": 4000, "end_ms": 6000, "caption": "Feature"}
    assets = [FakeAsset("asset-feature", Path("assets/feature.mp4"), 8000)]

    def window_scorer(asset, start_ms: int, end_ms: int) -> float:
        return 0.95 if start_ms == 6000 and end_ms == 8000 else 0.1

    result = match_segments([segment], assets, window_scorer=window_scorer)

    validate_matches(result)
    match = result["matches"][0]
    assert match["source_start_ms"] == 6000
    assert match["source_end_ms"] == 8000
    assert match["scores"]["window"] == 0.95
    assert any("window-score:0.950" in item for item in match["evidence"])


def test_match_segments_uses_same_role_aliases_as_material_diagnosis():
    assets = [
        FakeAsset("asset-other", Path("assets/other.mp4"), 5000),
        FakeAsset("asset-feature", Path("assets/product-detail.mp4"), 5000),
    ]

    result = match_segments([_segments()[1]], assets)

    match = result["matches"][0]
    assert match["status"] == "selected"
    assert match["asset_id"] == "asset-feature"
    assert match["confidence"] >= 0.9
    assert any("filename-role:feature" in item for item in match["evidence"])


def test_match_segments_uses_low_confidence_fallback_when_role_not_found():
    assets = [FakeAsset("asset-any", Path("assets/any.mp4"), 5000)]

    result = match_segments([_segments()[0]], assets, threshold=0.8)

    validate_matches(result)
    match = result["matches"][0]
    assert match["status"] == "low_confidence"
    assert match["asset_id"] == "asset-any"
    assert match["confidence"] < 0.8


def test_match_segments_marks_missing_when_asset_duration_too_short():
    assets = [FakeAsset("asset-short", Path("assets/hook.mp4"), 500)]

    result = match_segments([_segments()[0]], assets)

    assert result["matches"][0]["status"] == "missing"
    assert "duration" in result["matches"][0]["missing_reason"]


def test_apply_match_overrides_replaces_one_segment_by_id():
    segments = _segments()
    assets = [
        FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000),
        FakeAsset("asset-feature", Path("assets/feature.mp4"), 5000),
        FakeAsset("asset-manual", Path("assets/manual-clean-demo.mp4"), 5000),
    ]
    matches = match_segments(segments, assets)
    override_fn = getattr(matcher_module, "apply_match_overrides", None)

    assert override_fn is not None, "matcher should expose apply_match_overrides"
    result = override_fn(
        segments,
        matches,
        assets,
        {"version": "0.1", "segments": {"seg-002": {"asset_path": "assets/manual-clean-demo.mp4"}}},
    )

    validate_matches(result)
    by_segment = {match["segment_id"]: match for match in result["matches"]}
    assert by_segment["seg-001"]["asset_id"] == matches["matches"][0]["asset_id"]
    assert by_segment["seg-002"]["asset_id"] == "asset-manual"
    assert by_segment["seg-002"]["source_path"] == "assets/manual-clean-demo.mp4"
    assert by_segment["seg-002"]["confidence"] == 1.0
    assert "override:seg-002" in by_segment["seg-002"]["evidence"]
    assert by_segment["seg-002"]["scores"]["override"] == 1.0


def test_apply_match_overrides_can_pin_role_and_source_window():
    segment = {"id": "seg-002", "role": "feature", "start_ms": 1000, "end_ms": 2500, "caption": "Feature"}
    assets = [
        FakeAsset("asset-feature", Path("assets/feature.mp4"), 5000),
        FakeAsset("asset-manual", Path("assets/manual-demo.mp4"), 6000),
    ]
    matches = match_segments([segment], assets)
    override_fn = getattr(matcher_module, "apply_match_overrides", None)

    assert override_fn is not None, "matcher should expose apply_match_overrides"
    result = override_fn(
        [segment],
        matches,
        assets,
        {"segments": {"feature": {"asset_path": "assets/manual-demo.mp4", "source_start_ms": 2000}}},
    )

    match = result["matches"][0]
    assert match["asset_id"] == "asset-manual"
    assert match["source_start_ms"] == 2000
    assert match["source_end_ms"] == 3500
    assert "override:role:feature" in match["evidence"]


def test_apply_match_overrides_rejects_unknown_asset_path():
    override_fn = getattr(matcher_module, "apply_match_overrides", None)

    assert override_fn is not None, "matcher should expose apply_match_overrides"
    try:
        override_fn(
            _segments(),
            match_segments(_segments(), [FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000)]),
            [FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000)],
            {"segments": {"seg-002": {"asset_path": "assets/missing.mp4"}}},
        )
    except ValueError as exc:
        assert "assets/missing.mp4" in str(exc)
    else:
        raise AssertionError("unknown override asset should fail")


def test_apply_match_overrides_rejects_unknown_target():
    override_fn = getattr(matcher_module, "apply_match_overrides", None)

    assert override_fn is not None, "matcher should expose apply_match_overrides"
    try:
        override_fn(
            _segments(),
            match_segments(_segments(), [FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000)]),
            [FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000)],
            {"segments": {"seg-999": {"asset_path": "assets/hook.mp4"}}},
        )
    except ValueError as exc:
        assert "seg-999" in str(exc)
        assert "target" in str(exc)
    else:
        raise AssertionError("unknown override target should fail")


def test_apply_match_overrides_ignores_blank_template_entries():
    segments = _segments()
    assets = [
        FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000),
        FakeAsset("asset-feature", Path("assets/feature.mp4"), 5000),
    ]
    matches = match_segments(segments, assets)
    override_fn = getattr(matcher_module, "apply_match_overrides", None)

    assert override_fn is not None, "matcher should expose apply_match_overrides"
    result = override_fn(
        segments,
        matches,
        assets,
        {"segments": {"seg-002": {"asset_path": "", "candidate_asset_paths": ["assets/other.mp4"]}}},
    )

    assert result == matches


def test_build_recipe_adds_match_ids_and_validates_schema():
    assets = [
        FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000),
        FakeAsset("asset-feature", Path("assets/feature.mp4"), 5000),
    ]
    segments = _segments()
    matches = match_segments(segments, assets)

    recipe = build_recipe(
        "product",
        {"width": 1080, "height": 1920, "fps": 30},
        segments,
        matches,
        output_path=Path("work/remix.mp4"),
    )

    validate_recipe(recipe)
    assert recipe["duration_ms"] == 2500
    assert recipe["audio_strategy"] == "silent-preview"
    assert recipe["output_path"] == "work/remix.mp4"
    assert [segment["match_id"] for segment in recipe["segments"]] == ["match-001", "match-002"]
    assert "reference" not in str(recipe).lower()


def test_build_recipe_can_include_voiceover_and_caption_burn_in():
    assets = [FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000)]
    segment = _segments()[0]
    matches = match_segments([segment], assets)

    recipe = build_recipe(
        "product",
        {"width": 1080, "height": 1920, "fps": 30},
        [segment],
        matches,
        voiceover_path=Path("work/voiceover.wav"),
        caption_burn_in=True,
        audio_strategy="voiceover-only",
    )

    validate_recipe(recipe)
    assert recipe["audio_strategy"] == "voiceover-only"
    assert recipe["voiceover_path"] == "work/voiceover.wav"
    assert recipe["caption_burn_in"] is True


def test_build_recipe_preserves_existing_match_id_when_present():
    segment = {"id": "seg-001", "role": "hook", "start_ms": 0, "end_ms": 1000, "match_id": "custom", "caption": ""}
    matches = {"version": "0.1", "matches": [{"id": "custom", "segment_id": "seg-001", "status": "missing", "confidence": 0, "scores": {}, "candidates": [], "evidence": [], "missing_reason": "none"}]}

    recipe = build_recipe("product", {"width": 1080, "height": 1920, "fps": 30}, [segment], matches)

    assert recipe["segments"][0]["match_id"] == "custom"


def test_retime_recipe_and_matches_scales_timeline_without_changing_assets():
    assets = [
        FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000),
        FakeAsset("asset-feature", Path("assets/feature.mp4"), 5000),
    ]
    segments = _segments()
    matches = match_segments(segments, assets)
    recipe = build_recipe("product", {"width": 1080, "height": 1920, "fps": 30}, segments, matches)

    retimed_recipe, retimed_matches = retime_recipe_and_matches(recipe, matches, 2000)

    validate_recipe(retimed_recipe)
    validate_matches(retimed_matches)
    assert retimed_recipe["duration_ms"] == 2000
    assert [(item["start_ms"], item["end_ms"]) for item in retimed_recipe["segments"]] == [(0, 800), (800, 2000)]
    assert [(item["source_end_ms"] - item["source_start_ms"]) for item in retimed_matches["matches"]] == [800, 1200]
    assert retimed_matches["matches"][0]["source_start_ms"] == matches["matches"][0]["source_start_ms"]
    assert retimed_matches["matches"][1]["source_start_ms"] == matches["matches"][1]["source_start_ms"]
    assert [item["asset_id"] for item in retimed_matches["matches"]] == ["asset-hook", "asset-feature"]


def test_retime_recipe_and_matches_clamps_source_window_to_asset_duration():
    segment = {"id": "seg-001", "role": "feature", "start_ms": 4000, "end_ms": 6000, "caption": "Feature"}
    matches = match_segments([segment], [FakeAsset("asset-feature", Path("assets/feature.mp4"), 7000)])
    recipe = build_recipe("product", {"width": 1080, "height": 1920, "fps": 30}, [segment], matches)

    retimed_recipe, retimed_matches = retime_recipe_and_matches(recipe, matches, 5000)

    validate_recipe(retimed_recipe)
    validate_matches(retimed_matches)
    match = retimed_matches["matches"][0]
    assert match["source_end_ms"] == 7000
    assert match["source_start_ms"] == 2000
    assert match["source_end_ms"] - match["source_start_ms"] == 5000
