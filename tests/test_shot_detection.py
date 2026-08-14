from pathlib import Path

import pytest

from jianji_flow.contracts import validate_matches
from jianji_flow.shot_detection import (
    build_multi_shot_matches,
    detect_scene_boundaries,
    synchronize_shot_plan,
)


def _matches() -> dict:
    return {
        "version": "0.1",
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-a",
                "source_path": "assets/IMG_001.mp4",
                "source_start_ms": 0,
                "source_end_ms": 3000,
                "asset_duration_ms": 5000,
                "confidence": 0.9,
                "scores": {"filename": 0.9},
                "candidates": [],
                "evidence": ["filename-role:hook"],
            }
        ],
    }


def test_detect_scene_boundaries_parses_showinfo_and_bounds_candidates(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")

    class Result:
        returncode = 0
        stderr = "pts_time:0.733333\npts_time:1.633333\npts_time:3.233333\npts_time:4.166667\n"

    monkeypatch.setattr("jianji_flow.shot_detection.subprocess.run", lambda *args, **kwargs: Result())

    assert detect_scene_boundaries(source, 0, 7581, max_shots=4) == [0, 1633, 3233, 4167, 7581]


def test_detect_scene_boundaries_rejects_invalid_limits(tmp_path):
    with pytest.raises(ValueError, match="positive"):
        detect_scene_boundaries(tmp_path / "clip.mp4", 1000, 500, min_shot_ms=900)
    with pytest.raises(ValueError, match="at least 2"):
        detect_scene_boundaries(tmp_path / "clip.mp4", 0, 3000, max_shots=1)


def test_build_multi_shot_matches_attaches_structural_shots_and_plan():
    segments = [{"id": "seg-001", "start_ms": 0, "end_ms": 3000, "role": "hook", "caption": "开头"}]

    updated, plan = build_multi_shot_matches(
        segments,
        _matches(),
        detector=lambda path, start, end: [start, start + 1000, end],
    )

    match = updated["matches"][0]
    validate_matches(updated)
    assert [shot["source_start_ms"] for shot in match["shots"]] == [0, 1000]
    assert [shot["source_end_ms"] for shot in match["shots"]] == [1000, 3000]
    assert "multi-shot:2" in match["evidence"]
    assert plan["total_shots"] == 2
    assert plan["segments"][0]["status"] == "detected"


def test_build_multi_shot_falls_back_without_mutating_parent_match():
    segments = [{"id": "seg-001", "start_ms": 0, "end_ms": 3000, "role": "hook", "caption": "开头"}]

    def broken_detector(path: Path, start: int, end: int) -> list[int]:
        raise RuntimeError("ffmpeg unavailable")

    updated, plan = build_multi_shot_matches(segments, _matches(), detector=broken_detector)

    assert "shots" not in updated["matches"][0]
    assert plan["status"] == "warning"
    assert plan["segments"] == [{"segment_id": "seg-001", "shot_count": 1, "status": "fallback"}]


def test_build_multi_shot_skips_low_confidence_match_with_explicit_warning():
    matches = _matches()
    matches["matches"][0]["status"] = "low_confidence"

    updated, plan = build_multi_shot_matches(
        [{"id": "seg-001", "start_ms": 0, "end_ms": 3000, "role": "hook", "caption": "开头"}],
        matches,
        detector=lambda path, start, end: [start, start + 1000, end],
    )

    assert "shots" not in updated["matches"][0]
    assert plan["status"] == "warning"
    assert plan["total_shots"] == 1
    assert plan["segments"] == [
        {"segment_id": "seg-001", "shot_count": 1, "status": "skipped_low_confidence"}
    ]
    assert "visual review is required" in plan["warnings"][0]


def test_synchronize_shot_plan_preserves_low_confidence_skip_status():
    plan = {
        "version": "0.1",
        "status": "warning",
        "total_shots": 1,
        "segments": [{"segment_id": "seg-001", "shot_count": 1, "status": "skipped_low_confidence"}],
        "warnings": ["visual review is required"],
        "limits": {"min_shot_ms": 900, "max_shots": 4},
    }

    refreshed = synchronize_shot_plan(
        plan,
        {"matches": [{"segment_id": "seg-001", "status": "low_confidence"}]},
    )

    assert refreshed["segments"] == [
        {"segment_id": "seg-001", "shot_count": 1, "status": "skipped_low_confidence"}
    ]


def test_build_multi_shot_warns_when_adjacent_segments_repeat_same_shot_sequence():
    matches = _matches()
    matches["matches"].append(
        {
            **matches["matches"][0],
            "id": "match-002",
            "segment_id": "seg-002",
        }
    )

    updated, plan = build_multi_shot_matches(
        [
            {"id": "seg-001", "start_ms": 0, "end_ms": 3000, "role": "hook", "caption": "开头"},
            {"id": "seg-002", "start_ms": 3000, "end_ms": 6000, "role": "evidence", "caption": "证明"},
        ],
        matches,
        detector=lambda path, start, end: [start, start + 1000, end],
    )

    assert len(updated["matches"]) == 2
    assert plan["status"] == "warning"
    assert any("repeat the same source shot sequence" in warning for warning in plan["warnings"])


def test_synchronize_shot_plan_uses_final_retimed_ranges():
    plan = {
        "version": "0.1",
        "status": "pass",
        "total_shots": 2,
        "segments": [
            {
                "segment_id": "seg-001",
                "shot_count": 2,
                "status": "detected",
                "boundaries_ms": [1000, 2000, 3000],
            }
        ],
        "warnings": [],
        "limits": {"min_shot_ms": 900, "max_shots": 4},
    }
    matches = {
        "matches": [
            {
                "segment_id": "seg-001",
                "shots": [
                    {"source_start_ms": 1200, "source_end_ms": 1950},
                    {"source_start_ms": 1950, "source_end_ms": 2800},
                ],
            }
        ]
    }

    refreshed = synchronize_shot_plan(plan, matches)

    assert refreshed["total_shots"] == 2
    assert refreshed["segments"][0]["boundaries_ms"] == [1200, 1950, 2800]
    assert plan["segments"][0]["boundaries_ms"] == [1000, 2000, 3000]
