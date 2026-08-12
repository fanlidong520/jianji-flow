from dataclasses import dataclass
from pathlib import Path

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
    assert [(item["source_start_ms"], item["source_end_ms"]) for item in retimed_matches["matches"]] == [
        (0, 800),
        (0, 1200),
    ]
    assert [item["asset_id"] for item in retimed_matches["matches"]] == ["asset-hook", "asset-feature"]
