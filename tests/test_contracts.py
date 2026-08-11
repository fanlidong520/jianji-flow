from copy import deepcopy

import pytest
from jsonschema.exceptions import ValidationError

from jianji_flow.contracts import (
    validate_manifest,
    validate_matches,
    validate_recipe,
)


def valid_manifest():
    return {
        "version": "0.1",
        "asset_root": "assets",
        "reference": "reference.mp4",
        "assets": [
            {
                "asset_id": "asset-001",
                "path": "assets/product-demo.mp4",
                "sha256": "a" * 64,
                "media_type": "video",
                "duration_ms": 3000,
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "has_audio": True,
            }
        ],
    }


def valid_recipe():
    return {
        "version": "0.1",
        "mode": "product",
        "duration_ms": 3000,
        "target": {"width": 1080, "height": 1920, "fps": 30},
        "audio_strategy": "silent-preview",
        "segments": [
            {
                "id": "seg-001",
                "role": "hook",
                "start_ms": 0,
                "end_ms": 3000,
                "match_id": "match-001",
                "caption": "核心卖点",
            }
        ],
    }


def valid_matches():
    return {
        "version": "0.1",
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "source_path": "assets/product-demo.mp4",
                "source_start_ms": 0,
                "source_end_ms": 3000,
                "confidence": 0.82,
                "scores": {"visual": 0.9},
                "candidates": [],
                "evidence": ["role:hook", "visual:product"],
            }
        ],
    }


@pytest.mark.parametrize(
    ("validator", "factory"),
    [
        (validate_manifest, valid_manifest),
        (validate_recipe, valid_recipe),
        (validate_matches, valid_matches),
    ],
)
def test_valid_minimal_data_passes(validator, factory):
    validator(factory())


@pytest.mark.parametrize(
    ("validator", "factory"),
    [
        (validate_manifest, valid_manifest),
        (validate_recipe, valid_recipe),
        (validate_matches, valid_matches),
    ],
)
def test_unknown_top_level_fields_fail(validator, factory):
    data = factory()
    data["unexpected"] = True

    with pytest.raises(ValidationError):
        validator(data)


@pytest.mark.parametrize(
    ("validator", "factory", "path"),
    [
        (validate_manifest, valid_manifest, ("assets", 0, "unexpected")),
        (validate_recipe, valid_recipe, ("segments", 0, "unexpected")),
        (validate_matches, valid_matches, ("matches", 0, "unexpected")),
    ],
)
def test_unknown_nested_fields_fail(validator, factory, path):
    data = factory()
    current = data
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = True

    with pytest.raises(ValidationError):
        validator(data)


def test_float_times_fail():
    data = valid_recipe()
    data["segments"][0]["start_ms"] = 0.1

    with pytest.raises(ValidationError):
        validate_recipe(data)


def test_manifest_float_duration_fails():
    data = valid_manifest()
    data["assets"][0]["duration_ms"] = 3000.5

    with pytest.raises(ValidationError):
        validate_manifest(data)


def test_match_float_source_time_fails():
    data = valid_matches()
    data["matches"][0]["source_start_ms"] = 0.5

    with pytest.raises(ValidationError):
        validate_matches(data)


def test_invalid_mode_fails():
    data = valid_recipe()
    data["mode"] = "bad"

    with pytest.raises(ValidationError):
        validate_recipe(data)


@pytest.mark.parametrize(
    ("validator", "factory"),
    [
        (validate_manifest, valid_manifest),
        (validate_recipe, valid_recipe),
        (validate_matches, valid_matches),
    ],
)
def test_version_must_be_exact_v0_1(validator, factory):
    data = factory()
    data["version"] = "0.2"

    with pytest.raises(ValidationError):
        validator(data)


def test_recipe_rejects_unsupported_audio_strategy():
    data = valid_recipe()
    data["audio_strategy"] = "preserve-asset"

    with pytest.raises(ValidationError):
        validate_recipe(data)


def test_recipe_allows_voiceover_only_outputs():
    data = valid_recipe()
    data["audio_strategy"] = "voiceover-only"
    data["voiceover_path"] = "work/voiceover.wav"
    data["caption_burn_in"] = True

    validate_recipe(data)


def test_recipe_voiceover_only_requires_voiceover_path():
    data = valid_recipe()
    data["audio_strategy"] = "voiceover-only"
    data["caption_burn_in"] = True

    with pytest.raises(ValidationError):
        validate_recipe(data)


def test_recipe_voiceover_only_requires_caption_burn_in():
    data = valid_recipe()
    data["audio_strategy"] = "voiceover-only"
    data["voiceover_path"] = "work/voiceover.wav"

    with pytest.raises(ValidationError):
        validate_recipe(data)


def test_manifest_rejects_unsupported_media_type():
    data = valid_manifest()
    data["assets"][0]["media_type"] = "image"

    with pytest.raises(ValidationError):
        validate_manifest(data)


def test_recipe_allows_optional_output_path():
    data = valid_recipe()
    data["output_path"] = "work/remix.mp4"

    validate_recipe(data)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_outside_unit_interval_fails(confidence):
    data = valid_matches()
    data["matches"][0]["confidence"] = confidence

    with pytest.raises(ValidationError):
        validate_matches(data)


def test_missing_match_status_fails():
    data = valid_matches()
    del data["matches"][0]["status"]

    with pytest.raises(ValidationError):
        validate_matches(data)


def test_selected_requires_source_structure():
    data = valid_matches()
    del data["matches"][0]["source_end_ms"]

    with pytest.raises(ValidationError):
        validate_matches(data)


def test_match_rejects_second_timeline_fields():
    data = valid_matches()
    data["matches"][0]["target_start_ms"] = 0

    with pytest.raises(ValidationError):
        validate_matches(data)


def test_candidate_requires_traceable_structure():
    data = valid_matches()
    data["matches"][0]["candidates"] = [{}]

    with pytest.raises(ValidationError):
        validate_matches(data)


def test_candidate_float_time_fails():
    data = valid_matches()
    data["matches"][0]["candidates"] = [
        {
            "asset_id": "asset-002",
            "source_path": "assets/candidate.mp4",
            "source_start_ms": 0.5,
            "source_end_ms": 1000,
            "score": 0.5,
            "evidence": [],
        }
    ]

    with pytest.raises(ValidationError):
        validate_matches(data)


@pytest.mark.parametrize(
    ("validator", "factory", "field"),
    [
        (validate_manifest, valid_manifest, "assets"),
        (validate_recipe, valid_recipe, "segments"),
        (validate_matches, valid_matches, "matches"),
    ],
)
def test_empty_core_arrays_fail(validator, factory, field):
    data = factory()
    data[field] = []

    with pytest.raises(ValidationError):
        validator(data)


def test_low_confidence_requires_source_structure():
    data = valid_matches()
    data["matches"][0]["status"] = "low_confidence"
    validate_matches(data)


def test_missing_requires_reason_and_forbids_source_structure():
    data = valid_matches()
    data["matches"][0] = {
        "id": "match-001",
        "segment_id": "seg-001",
        "status": "missing",
        "confidence": 0,
        "scores": {},
        "candidates": [],
        "evidence": [],
        "missing_reason": "no suitable asset",
    }
    validate_matches(data)

    invalid = deepcopy(data)
    invalid["matches"][0]["source_start_ms"] = 0
    with pytest.raises(ValidationError):
        validate_matches(invalid)


def test_rejected_requires_reason_and_has_distinct_structure():
    data = valid_matches()
    data["matches"][0] = {
        "id": "match-001",
        "segment_id": "seg-001",
        "status": "rejected",
        "confidence": 0.2,
        "scores": {},
        "candidates": [],
        "evidence": [],
        "rejected_reason": "not relevant",
    }
    validate_matches(data)

    invalid = deepcopy(data)
    invalid["matches"][0]["asset_id"] = "asset-001"
    with pytest.raises(ValidationError):
        validate_matches(invalid)
