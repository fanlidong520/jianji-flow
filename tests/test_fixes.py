from dataclasses import dataclass
from pathlib import Path

import jianji_flow.fixes as fixes_module


@dataclass(frozen=True)
class FakeAsset:
    asset_id: str
    path: Path
    duration_ms: int


def test_build_fixes_template_focuses_weak_story_segments():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook"},
            {"id": "seg-002", "role": "feature", "match_id": "match-002", "caption": "Feature"},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-hook",
                "source_path": "assets/hook.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:hook"],
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "status": "selected",
                "asset_id": "asset-feature",
                "source_path": "assets/feature.mp4",
                "confidence": 0.92,
                "evidence": ["visual-frame:matches-caption"],
            },
        ]
    }
    review = {
        "story_support": {
            "weak_evidence_roles": ["hook"],
        }
    }
    assets = [
        FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000),
        FakeAsset("asset-better-hook", Path("assets/new-hook-demo.mp4"), 5000),
        FakeAsset("asset-feature", Path("assets/feature.mp4"), 5000),
    ]

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review)

    assert template["version"] == "0.1"
    assert "seg-001" in template["segments"]
    assert "seg-002" not in template["segments"]
    segment = template["segments"]["seg-001"]
    assert segment["role"] == "hook"
    assert segment["caption"] == "Hook"
    assert segment["current_asset_path"] == "assets/hook.mp4"
    assert segment["asset_path"] == ""
    assert segment["reason"] == "weak story evidence"
    assert "assets/new-hook-demo.mp4" in segment["candidate_asset_paths"]
    assert "assets/hook.mp4" not in segment["candidate_asset_paths"]


def test_build_fixes_template_includes_low_confidence_segments():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook"},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "low_confidence",
                "asset_id": "asset-any",
                "source_path": "assets/any.mp4",
                "confidence": 0.55,
                "evidence": ["fallback:first-available"],
            },
        ]
    }
    assets = [
        FakeAsset("asset-any", Path("assets/any.mp4"), 5000),
        FakeAsset("asset-hook", Path("assets/hook-closeup.mp4"), 5000),
    ]

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, {"story_support": {"weak_evidence_roles": []}})

    segment = template["segments"]["seg-001"]
    assert segment["reason"] == "low confidence match"
    assert segment["candidate_asset_paths"] == ["assets/hook-closeup.mp4"]


def test_build_fixes_template_does_not_recommend_wrong_role_when_role_has_no_alternative():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook"},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-hook",
                "source_path": "assets/hook.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:hook"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["hook"]}}
    assets = [
        FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000),
        FakeAsset("asset-feature", Path("assets/feature.mp4"), 5000),
        FakeAsset("asset-cta", Path("assets/cta.mp4"), 5000),
    ]

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review)

    segment = template["segments"]["seg-001"]
    assert segment["recommended_asset_path"] == ""
    assert segment["recommendation_status"] == "no_candidate"
    assert segment["recommendation_warnings"] == ["no role-matching candidate"]
    assert segment["candidate_asset_paths"] == ["assets/feature.mp4", "assets/cta.mp4"]
    assert all(
        any("role mismatch" in warning for warning in candidate["warnings"])
        for candidate in segment["candidate_assets"]
    )


def test_build_fixes_template_ranks_non_adjacent_candidates_first():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook", "start_ms": 0, "end_ms": 1000},
            {"id": "seg-002", "role": "feature", "match_id": "match-002", "caption": "Feature", "start_ms": 1000, "end_ms": 3000},
            {"id": "seg-003", "role": "evidence", "match_id": "match-003", "caption": "Evidence", "start_ms": 3000, "end_ms": 5000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-hook",
                "source_path": "assets/hook.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:hook"],
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "status": "selected",
                "asset_id": "asset-current",
                "source_path": "assets/current-feature.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
            {
                "id": "match-003",
                "segment_id": "seg-003",
                "status": "selected",
                "asset_id": "asset-adjacent",
                "source_path": "assets/feature-adjacent.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:evidence"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current", Path("assets/current-feature.mp4"), 6000),
        FakeAsset("asset-adjacent", Path("assets/feature-adjacent.mp4"), 6000),
        FakeAsset("asset-alt", Path("assets/feature-alt.mp4"), 6000),
        FakeAsset("asset-cta", Path("assets/cta.mp4"), 6000),
    ]

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review)

    segment = template["segments"]["seg-002"]
    assert segment["recommended_asset_path"] == "assets/feature-alt.mp4"
    assert segment["candidate_asset_paths"] == [
        "assets/feature-alt.mp4",
        "assets/cta.mp4",
        "assets/feature-adjacent.mp4",
    ]
    adjacent = next(item for item in segment["candidate_assets"] if item["asset_path"] == "assets/feature-adjacent.mp4")
    assert adjacent["warnings"] == ["would repeat adjacent segment"]
    assert "matches role feature" in segment["candidate_assets"][0]["reasons"]
    assert "avoids adjacent repetition" in segment["candidate_assets"][0]["reasons"]


def test_build_fixes_template_marks_warning_recommendation_as_best_available():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook", "start_ms": 0, "end_ms": 1000},
            {"id": "seg-002", "role": "feature", "match_id": "match-002", "caption": "Feature", "start_ms": 1000, "end_ms": 5000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-adjacent",
                "source_path": "assets/feature-adjacent.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:hook"],
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "status": "selected",
                "asset_id": "asset-current",
                "source_path": "assets/current-feature.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current", Path("assets/current-feature.mp4"), 6000),
        FakeAsset("asset-adjacent", Path("assets/feature-adjacent.mp4"), 6000),
        FakeAsset("asset-short", Path("assets/short-safe.mp4"), 3000),
    ]

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review)

    segment = template["segments"]["seg-002"]
    assert segment["recommended_asset_path"] == "assets/feature-adjacent.mp4"
    assert segment["recommendation_status"] == "best_available_with_warnings"
    assert segment["recommendation_warnings"] == ["would repeat adjacent segment"]


def test_build_fixes_template_warns_when_recommending_asset_already_recommended_for_another_segment():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature A", "start_ms": 0, "end_ms": 1000},
            {"id": "seg-002", "role": "feature", "match_id": "match-002", "caption": "Feature B", "start_ms": 1000, "end_ms": 2000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-current-a",
                "source_path": "assets/current-a.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "status": "selected",
                "asset_id": "asset-current-b",
                "source_path": "assets/current-b.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current-a", Path("assets/current-a.mp4"), 5000),
        FakeAsset("asset-current-b", Path("assets/current-b.mp4"), 5000),
        FakeAsset("asset-shared", Path("assets/shared-feature.mp4"), 5000),
    ]

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review)

    assert template["segments"]["seg-001"]["recommended_asset_path"] == "assets/shared-feature.mp4"
    assert template["segments"]["seg-001"]["recommendation_status"] == "recommended"
    assert template["segments"]["seg-002"]["recommended_asset_path"] == "assets/shared-feature.mp4"
    assert template["segments"]["seg-002"]["recommendation_status"] == "best_available_with_warnings"
    assert template["segments"]["seg-002"]["recommendation_warnings"] == ["already recommended for another segment"]


def test_build_fixes_template_prefers_visually_distinct_recommendation():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature", "start_ms": 0, "end_ms": 1000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-current",
                "source_path": "assets/current-feature.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current", Path("assets/current-feature.mp4"), 5000),
        FakeAsset("asset-copy", Path("assets/feature-copy.mp4"), 5000),
        FakeAsset("asset-distinct", Path("assets/feature-distinct.mp4"), 5000),
    ]

    def visually_similar(
        current_path: str,
        candidate_path: str,
        segment_duration_ms: int,
        current_start_ms: int,
        candidate_start_ms: int,
    ) -> bool:
        return candidate_path.endswith("feature-copy.mp4")

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review, visual_similarity_checker=visually_similar)

    segment = template["segments"]["seg-001"]
    assert segment["recommended_asset_path"] == "assets/feature-distinct.mp4"
    duplicate = next(item for item in segment["candidate_assets"] if item["asset_path"] == "assets/feature-copy.mp4")
    assert "visually similar to current segment" in duplicate["warnings"]
    assert duplicate["score"] < segment["candidate_assets"][0]["score"]


def test_build_fixes_template_marks_only_visual_duplicate_as_warning_recommendation():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature", "start_ms": 0, "end_ms": 1000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-current",
                "source_path": "assets/current-feature.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current", Path("assets/current-feature.mp4"), 5000),
        FakeAsset("asset-copy", Path("assets/feature-copy.mp4"), 5000),
    ]

    def visually_similar(
        current_path: str,
        candidate_path: str,
        segment_duration_ms: int,
        current_start_ms: int,
        candidate_start_ms: int,
    ) -> bool:
        return True

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review, visual_similarity_checker=visually_similar)

    segment = template["segments"]["seg-001"]
    assert segment["recommended_asset_path"] == "assets/feature-copy.mp4"
    assert segment["recommendation_status"] == "best_available_with_warnings"
    assert segment["recommendation_warnings"] == ["visually similar to current segment"]


def test_build_fixes_template_warns_when_visual_similarity_cannot_be_checked():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature", "start_ms": 0, "end_ms": 1000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-current",
                "source_path": "assets/current-feature.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current", Path("assets/current-feature.mp4"), 5000),
        FakeAsset("asset-copy", Path("assets/feature-copy.mp4"), 5000),
    ]

    def broken_visual_checker(
        current_path: str,
        candidate_path: str,
        segment_duration_ms: int,
        current_start_ms: int,
        candidate_start_ms: int,
    ) -> bool:
        raise RuntimeError("frame extraction failed")

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review, visual_similarity_checker=broken_visual_checker)

    segment = template["segments"]["seg-001"]
    assert segment["recommended_asset_path"] == "assets/feature-copy.mp4"
    assert segment["recommendation_status"] == "best_available_with_warnings"
    assert segment["recommendation_warnings"] == ["visual similarity check failed"]
    assert segment["candidate_assets"][0]["warnings"] == ["visual similarity check failed"]


def test_build_fixes_template_passes_current_source_window_to_visual_checker():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature", "start_ms": 0, "end_ms": 1000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-current",
                "source_path": "assets/current-feature.mp4",
                "source_start_ms": 2200,
                "source_end_ms": 3200,
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current", Path("assets/current-feature.mp4"), 5000),
        FakeAsset("asset-alt", Path("assets/feature-alt.mp4"), 5000),
    ]
    calls = []

    def visually_similar(
        current_path: str,
        candidate_path: str,
        segment_duration_ms: int,
        current_start_ms: int,
        candidate_start_ms: int,
    ) -> bool:
        calls.append((current_path, candidate_path, segment_duration_ms, current_start_ms, candidate_start_ms))
        return False

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template_fn(recipe, matches, assets, review, visual_similarity_checker=visually_similar)

    assert calls == [("assets/current-feature.mp4", "assets/feature-alt.mp4", 1000, 2200, 2200)]


def test_build_fixes_template_uses_current_source_duration_for_visual_check_when_minimum_duration_is_longer():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    final_recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature", "start_ms": 0, "end_ms": 1000},
        ]
    }
    pretime_recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature", "start_ms": 0, "end_ms": 5000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-current",
                "source_path": "assets/current-feature.mp4",
                "source_start_ms": 2000,
                "source_end_ms": 3000,
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current", Path("assets/current-feature.mp4"), 8000),
        FakeAsset("asset-alt", Path("assets/feature-alt.mp4"), 8000),
    ]
    calls = []

    def visually_similar(
        current_path: str,
        candidate_path: str,
        segment_duration_ms: int,
        current_start_ms: int,
        candidate_start_ms: int,
    ) -> bool:
        calls.append((segment_duration_ms, current_start_ms, candidate_start_ms))
        return False

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template_fn(
        final_recipe,
        matches,
        assets,
        review,
        minimum_duration_recipe=pretime_recipe,
        visual_similarity_checker=visually_similar,
    )

    assert calls == [(1000, 2000, 2000)]


def test_build_fixes_template_clamps_candidate_visual_start_to_asset_duration():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature", "start_ms": 0, "end_ms": 1000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-current",
                "source_path": "assets/current-feature.mp4",
                "source_start_ms": 4200,
                "source_end_ms": 5200,
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current", Path("assets/current-feature.mp4"), 8000),
        FakeAsset("asset-alt", Path("assets/feature-alt.mp4"), 3000),
    ]
    calls = []

    def visually_similar(
        current_path: str,
        candidate_path: str,
        segment_duration_ms: int,
        current_start_ms: int,
        candidate_start_ms: int,
    ) -> bool:
        calls.append((segment_duration_ms, current_start_ms, candidate_start_ms))
        return False

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template_fn(recipe, matches, assets, review, visual_similarity_checker=visually_similar)

    assert calls == [(1000, 4200, 2000)]


def test_build_fixes_template_skips_visual_check_for_wrong_role_fallbacks():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "match_id": "match-001", "caption": "Feature", "start_ms": 0, "end_ms": 1000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-current",
                "source_path": "assets/current-feature.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-current", Path("assets/current-feature.mp4"), 5000),
        FakeAsset("asset-wrong", Path("assets/cta-wrong.mp4"), 5000),
        FakeAsset("asset-alt", Path("assets/feature-alt.mp4"), 5000),
    ]
    checked_candidates = []

    def visually_similar(
        current_path: str,
        candidate_path: str,
        segment_duration_ms: int,
        current_start_ms: int,
        candidate_start_ms: int,
    ) -> bool:
        checked_candidates.append(candidate_path)
        return False

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review, visual_similarity_checker=visually_similar)

    assert checked_candidates == ["assets/feature-alt.mp4"]
    wrong_role = next(item for item in template["segments"]["seg-001"]["candidate_assets"] if item["asset_path"] == "assets/cta-wrong.mp4")
    assert "role mismatch; filename-only fallback" in wrong_role["warnings"]
    assert "visually distinct from current segment" not in wrong_role["reasons"]


def test_build_fixes_template_filters_candidates_shorter_than_segment():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "hook", "match_id": "match-001", "caption": "Hook", "start_ms": 0, "end_ms": 4000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-hook",
                "source_path": "assets/hook.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:hook"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["hook"]}}
    assets = [
        FakeAsset("asset-hook", Path("assets/hook.mp4"), 5000),
        FakeAsset("asset-short", Path("assets/short.mp4"), 3000),
        FakeAsset("asset-long", Path("assets/long.mp4"), 6000),
    ]

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(recipe, matches, assets, review)

    assert template["segments"]["seg-001"]["candidate_asset_paths"] == ["assets/long.mp4"]


def test_build_fixes_template_can_filter_by_preretime_segment_duration():
    template_fn = getattr(fixes_module, "build_fixes_template", None)
    final_recipe = {
        "segments": [
            {"id": "seg-003", "role": "feature", "match_id": "match-003", "caption": "Feature", "start_ms": 0, "end_ms": 2000},
        ]
    }
    pretime_recipe = {
        "segments": [
            {"id": "seg-003", "role": "feature", "match_id": "match-003", "caption": "Feature", "start_ms": 10000, "end_ms": 20000},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-003",
                "segment_id": "seg-003",
                "status": "selected",
                "asset_id": "asset-feature",
                "source_path": "assets/feature.mp4",
                "confidence": 0.92,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    review = {"story_support": {"weak_evidence_roles": ["feature"]}}
    assets = [
        FakeAsset("asset-feature", Path("assets/feature.mp4"), 12000),
        FakeAsset("asset-short", Path("assets/short.mp4"), 3000),
        FakeAsset("asset-long", Path("assets/long.mp4"), 11000),
    ]

    assert template_fn is not None, "fixes module should expose build_fixes_template"
    template = template_fn(final_recipe, matches, assets, review, minimum_duration_recipe=pretime_recipe)

    assert template["segments"]["seg-003"]["candidate_asset_paths"] == ["assets/long.mp4"]


def test_build_recommended_fixes_applies_clean_segment_recommendation_only():
    build_recommended = getattr(fixes_module, "build_recommended_fixes", None)
    fixes = {
        "version": "0.1",
        "segments": {
            "seg-001": {
                "asset_path": "",
                "recommended_asset_path": "assets/hook-alt.mp4",
                "recommendation_status": "recommended",
                "recommendation_warnings": [],
            },
            "seg-002": {
                "asset_path": "",
                "recommended_asset_path": "assets/feature-alt.mp4",
                "recommendation_status": "best_available_with_warnings",
                "recommendation_warnings": ["would repeat adjacent segment"],
            },
        },
    }

    assert build_recommended is not None, "fixes module should expose build_recommended_fixes"
    result = build_recommended(fixes, "seg-001")

    assert result == {
        "version": "0.1",
        "segments": {
            "seg-001": {
                "asset_path": "assets/hook-alt.mp4",
            }
        },
    }


def test_build_recommended_fixes_rejects_warning_recommendation():
    build_recommended = getattr(fixes_module, "build_recommended_fixes", None)
    fixes = {
        "version": "0.1",
        "segments": {
            "seg-002": {
                "asset_path": "",
                "recommended_asset_path": "assets/feature-alt.mp4",
                "recommendation_status": "best_available_with_warnings",
                "recommendation_warnings": ["would repeat adjacent segment"],
            },
        },
    }

    assert build_recommended is not None, "fixes module should expose build_recommended_fixes"
    try:
        build_recommended(fixes, "seg-002")
    except ValueError as exc:
        assert "best_available_with_warnings" in str(exc)
        assert "would repeat adjacent segment" in str(exc)
    else:
        raise AssertionError("warning recommendation should not be auto-applied")
