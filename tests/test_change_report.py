from pathlib import Path

from PIL import Image

from jianji_flow.change_report import build_change_report


def test_build_change_report_lists_changed_and_unchanged_segments(tmp_path: Path, monkeypatch):
    calls = []

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        calls.append((video_path.as_posix(), frame_path.name, time_ms))
        color = "black" if "before" in frame_path.name else "white"
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (16, 16), color).save(frame_path)

    monkeypatch.setattr("jianji_flow.change_report._extract_frame", fake_extract_frame)
    recipe = {
        "segments": [
            {
                "id": "seg-001",
                "role": "hook",
                "caption": "Open with the product",
                "match_id": "match-001",
                "start_ms": 0,
                "end_ms": 1000,
            },
            {
                "id": "seg-002",
                "role": "feature",
                "caption": "Show the detail",
                "match_id": "match-002",
                "start_ms": 1000,
                "end_ms": 2600,
            },
        ]
    }
    before_matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "source_path": "assets/01-hook.mp4",
                "source_start_ms": 0,
                "source_end_ms": 1000,
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "source_path": "assets/03-feature.mp4",
                "source_start_ms": 0,
                "source_end_ms": 1600,
                "evidence": ["filename-role:feature"],
            },
        ]
    }
    after_matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "source_path": "assets/01-hook.mp4",
                "source_start_ms": 0,
                "source_end_ms": 1000,
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "source_path": "assets/05-cta.mp4",
                "source_start_ms": 200,
                "source_end_ms": 1800,
                "evidence": ["filename-role:feature", "override:seg-002"],
            },
        ]
    }

    report = build_change_report(
        recipe,
        before_matches,
        after_matches,
        diagnostics_dir=tmp_path / "change-diagnostics",
    )

    assert report == {
        "changed_segments": [
            {
                "segment_id": "seg-002",
                "role": "feature",
                "caption": "Show the detail",
                "before_asset": "assets/03-feature.mp4",
                "before_range": "0-1600ms",
                "before_frame": (tmp_path / "change-diagnostics" / "seg-002-before.png").as_posix(),
                "after_asset": "assets/05-cta.mp4",
                "after_range": "200-1800ms",
                "after_frame": (tmp_path / "change-diagnostics" / "seg-002-after.png").as_posix(),
                "visual_difference": 255.0,
                "reason": "override:seg-002",
            }
        ],
        "unchanged_segments": ["seg-001"],
        "unaccounted_segments": [],
    }
    assert calls == [
        ("assets/03-feature.mp4", "seg-002-before.png", 800),
        ("assets/05-cta.mp4", "seg-002-after.png", 1000),
    ]
    assert (tmp_path / "change-diagnostics" / "seg-002-before.png").exists()
    assert (tmp_path / "change-diagnostics" / "seg-002-after.png").exists()


def test_build_change_report_marks_difference_unavailable_when_sampling_fails(tmp_path: Path, monkeypatch):
    def fake_extract_frame(*args, **kwargs):
        raise RuntimeError("cannot decode frame")

    monkeypatch.setattr("jianji_flow.change_report._extract_frame", fake_extract_frame)
    recipe = {
        "segments": [
            {
                "id": "seg-001",
                "role": "feature",
                "caption": "Show another source window",
                "match_id": "match-001",
            }
        ]
    }
    before_matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "source_path": "assets/feature.mp4",
                "source_start_ms": 0,
                "source_end_ms": 1000,
            }
        ]
    }
    after_matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "source_path": "assets/feature.mp4",
                "source_start_ms": 2000,
                "source_end_ms": 3000,
                "evidence": ["override:seg-001"],
            }
        ]
    }

    report = build_change_report(
        recipe,
        before_matches,
        after_matches,
        diagnostics_dir=tmp_path / "change-diagnostics",
    )

    assert report["changed_segments"][0]["visual_difference"] is None
    assert report["changed_segments"][0]["visual_difference_warning"] == "cannot decode frame"


def test_build_change_report_lists_unaccounted_segments(tmp_path: Path):
    recipe = {
        "segments": [
            {"id": "seg-001", "role": "feature", "caption": "Missing after", "match_id": "match-001"},
            {"id": "seg-002", "role": "cta", "caption": "Missing before", "match_id": "match-002"},
        ]
    }
    before_matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "source_path": "assets/before.mp4",
                "source_start_ms": 0,
                "source_end_ms": 1000,
            }
        ]
    }
    after_matches = {
        "matches": [
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "source_path": "assets/after.mp4",
                "source_start_ms": 0,
                "source_end_ms": 1000,
            }
        ]
    }

    report = build_change_report(
        recipe,
        before_matches,
        after_matches,
        diagnostics_dir=tmp_path / "change-diagnostics",
    )

    assert report["changed_segments"] == []
    assert report["unchanged_segments"] == []
    assert report["unaccounted_segments"] == ["seg-001", "seg-002"]
