from pathlib import Path

import pytest

from jianji_flow.semantics import validate_semantics


def _inputs(tmp_path: Path):
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    source = asset_root / "clip.mp4"
    source.write_bytes(b"source media")
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"reference media")
    recipe = {
        "output_path": str(tmp_path / "work" / "remix.mp4"),
        "duration_ms": 3000,
        "segments": [
            {"id": "seg-1", "start_ms": 0, "end_ms": 1000, "match_id": "m-1"},
            {"id": "seg-2", "start_ms": 1000, "end_ms": 3000, "match_id": "m-2"},
        ],
    }
    matches = {
        "matches": [
            {
                "id": "m-1",
                "segment_id": "seg-1",
                "status": "selected",
                "asset_id": "a-1",
                "source_path": str(source),
                "source_start_ms": 0,
                "source_end_ms": 1000,
            },
            {
                "id": "m-2",
                "segment_id": "seg-2",
                "status": "selected",
                "asset_id": "a-1",
                "source_path": str(source),
                "source_start_ms": 1000,
                "source_end_ms": 3000,
            },
        ]
    }
    manifest = {
        "assets": [{"asset_id": "a-1", "path": str(source), "duration_ms": 3000}]
    }
    return recipe, matches, manifest, reference, asset_root


def _validate(tmp_path, recipe, matches, manifest):
    reference = tmp_path / "reference.mp4"
    asset_root = tmp_path / "assets"
    return validate_semantics(
        recipe, matches, manifest, str(reference), str(asset_root), str(tmp_path / "work")
    )


def test_valid_recipe_returns_no_errors(tmp_path):
    recipe, matches, manifest, reference, asset_root = _inputs(tmp_path)

    assert validate_semantics(
        recipe, matches, manifest, str(reference), str(asset_root), str(tmp_path / "work")
    ) == []


def test_missing_match_id_is_blocking(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    del recipe["segments"][0]["match_id"]

    assert any("match_id" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_timeline_must_start_at_zero(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    recipe["segments"][0]["start_ms"] = 100

    assert any("start at 0" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_timeline_gaps_and_overlaps_are_blocking(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    recipe["segments"][1]["start_ms"] = 1200
    errors = _validate(tmp_path, recipe, matches, manifest)
    assert any("gap" in error for error in errors)

    recipe["segments"][1]["start_ms"] = 900
    errors = _validate(tmp_path, recipe, matches, manifest)
    assert any("overlap" in error for error in errors)


def test_segment_end_must_be_after_start(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    recipe["segments"][0]["end_ms"] = 0

    assert any("greater than start_ms" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_final_segment_must_end_at_recipe_duration(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    recipe["segments"][-1]["end_ms"] = 2900

    assert any("duration_ms" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_selected_asset_id_must_exist_in_manifest(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    matches["matches"][0]["asset_id"] = "missing"

    assert any("asset_id" in error and "manifest" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_selected_source_range_must_fit_asset_duration(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    matches["matches"][0]["source_end_ms"] = 3001

    assert any("asset duration" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_source_range_duration_must_match_recipe_segment_duration(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    matches["matches"][0]["source_end_ms"] = 100

    assert any("source range duration" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_selected_source_path_must_be_inside_asset_root(tmp_path):
    recipe, matches, manifest, reference, asset_root = _inputs(tmp_path)
    outside = tmp_path / "outside.mp4"
    outside.touch()
    matches["matches"][0]["source_path"] = str(outside)

    errors = validate_semantics(recipe, matches, manifest, str(reference), str(asset_root), str(tmp_path / "work"))
    assert any("outside asset_root" in error for error in errors)


def test_selected_source_path_must_not_be_reference(tmp_path):
    recipe, matches, manifest, reference, asset_root = _inputs(tmp_path)
    matches["matches"][0]["source_path"] = str(reference)

    errors = validate_semantics(recipe, matches, manifest, str(reference), str(asset_root), str(tmp_path / "work"))
    assert any("reference_path" in error for error in errors)


def test_selected_source_file_must_not_match_reference_hash(tmp_path):
    recipe, matches, manifest, reference, asset_root = _inputs(tmp_path)
    reference.write_bytes(b"same media bytes")
    copied_reference = asset_root / "copied-reference.mp4"
    copied_reference.write_bytes(b"same media bytes")
    matches["matches"][0]["source_path"] = str(copied_reference)
    manifest["assets"][0]["path"] = str(copied_reference)

    errors = validate_semantics(recipe, matches, manifest, str(reference), str(asset_root), str(tmp_path / "work"))
    assert any("reference" in error and "hash" in error for error in errors)


def test_selected_source_hardlink_must_not_be_reference(tmp_path):
    recipe, matches, manifest, reference, asset_root = _inputs(tmp_path)
    hardlink = asset_root / "reference-hardlink.mp4"
    try:
        hardlink.hardlink_to(reference)
    except OSError:
        pytest.skip("hardlinks are not available on this filesystem")
    matches["matches"][0]["source_path"] = str(hardlink)
    manifest["assets"][0]["path"] = str(hardlink)

    errors = validate_semantics(recipe, matches, manifest, str(reference), str(asset_root), str(tmp_path / "work"))
    assert any("reference_path" in error or "hash" in error for error in errors)


def test_missing_match_used_by_recipe_is_blocking(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    matches["matches"][0] = {"id": "m-1", "status": "missing"}

    assert any("cannot be rendered" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_url_or_protocol_source_path_is_blocking(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    matches["matches"][0]["source_path"] = "https://example.com/clip.mp4"

    assert any("URL or protocol" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_unreferenced_match_source_path_is_still_validated(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    matches["matches"].append(
        {
            "id": "unreferenced",
            "segment_id": "seg-extra",
            "status": "selected",
            "asset_id": "a-1",
            "source_path": " https://example.com/clip.mp4",
            "source_start_ms": 0,
            "source_end_ms": 1000,
            "confidence": 0.9,
            "scores": {},
            "candidates": [],
            "evidence": [],
        }
    )

    assert any("unreferenced" in error and "URL or protocol" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_single_colon_protocol_source_path_is_blocking(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    matches["matches"][0]["source_path"] = "s3:clip.mp4"
    manifest["assets"][0]["path"] = "s3:clip.mp4"

    assert any("URL or protocol" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_single_slash_protocol_manifest_asset_path_is_blocking(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    matches["matches"][0]["source_path"] = "file:/tmp/clip.mp4"
    manifest["assets"][0]["path"] = "file:/tmp/clip.mp4"

    assert any("manifest asset" in error and "URL or protocol" in error for error in _validate(tmp_path, recipe, matches, manifest))


def test_match_source_path_must_match_manifest_asset_path(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    other = tmp_path / "assets" / "other.mp4"
    other.touch()
    matches["matches"][0]["source_path"] = str(other)

    errors = _validate(tmp_path, recipe, matches, manifest)
    assert any("manifest asset path" in error for error in errors)


def test_manifest_asset_path_must_not_be_reference(tmp_path):
    recipe, matches, manifest, reference, asset_root = _inputs(tmp_path)
    manifest["assets"][0]["path"] = str(reference)

    errors = validate_semantics(recipe, matches, manifest, str(reference), str(asset_root), str(tmp_path / "work"))
    assert any("manifest asset" in error and "reference_path" in error for error in errors)


def test_match_segment_id_must_match_recipe_segment_id(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    matches["matches"][0]["segment_id"] = "seg-other"

    errors = _validate(tmp_path, recipe, matches, manifest)
    assert any("segment_id" in error for error in errors)


def test_manifest_paths_must_match_function_arguments(tmp_path):
    recipe, matches, manifest, reference, asset_root = _inputs(tmp_path)
    manifest["asset_root"] = str(tmp_path / "different-assets")

    errors = validate_semantics(recipe, matches, manifest, str(reference), str(asset_root), str(tmp_path / "work"))
    assert any("manifest asset_root" in error for error in errors)

    manifest["asset_root"] = str(asset_root)
    manifest["reference"] = str(tmp_path / "different-reference.mp4")
    errors = validate_semantics(recipe, matches, manifest, str(reference), str(asset_root), str(tmp_path / "work"))
    assert any("manifest reference" in error for error in errors)


def test_recipe_output_path_must_stay_inside_work_dir(tmp_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    recipe["output_path"] = str(tmp_path / "outside" / "remix.mp4")

    errors = _validate(tmp_path, recipe, matches, manifest)
    assert any("work_dir" in error for error in errors)


@pytest.mark.parametrize("output_path", ["s3:remix.mp4", "file:/tmp/remix.mp4", "https://example.com/remix.mp4"])
def test_recipe_output_path_must_not_be_url_or_protocol(tmp_path, output_path):
    recipe, matches, manifest, *_ = _inputs(tmp_path)
    recipe["output_path"] = output_path

    errors = _validate(tmp_path, recipe, matches, manifest)
    assert any("output_path" in error and "URL or protocol" in error for error in errors)


@pytest.mark.parametrize(
    ("reference_path", "asset_root", "work_dir", "expected"),
    [
        ("s3:reference.mp4", None, None, "reference_path"),
        (None, "s3:assets", None, "asset_root"),
        (None, None, "s3:work", "work_dir"),
    ],
)
def test_semantic_path_arguments_must_not_be_url_or_protocol(
    tmp_path, reference_path, asset_root, work_dir, expected
):
    recipe, matches, manifest, valid_reference, valid_asset_root = _inputs(tmp_path)
    work = tmp_path / "work"

    errors = validate_semantics(
        recipe,
        matches,
        manifest,
        reference_path or str(valid_reference),
        asset_root or str(valid_asset_root),
        work_dir or str(work),
    )

    assert any(expected in error and "URL or protocol" in error for error in errors)
