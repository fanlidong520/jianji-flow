from jianji_flow.edit_diversity import diagnose_edit_diversity


def _recipe(segment_count: int) -> dict:
    return {
        "segments": [
            {"id": f"seg-{index:03d}", "match_id": f"match-{index:03d}"}
            for index in range(1, segment_count + 1)
        ]
    }


def _matches(paths: list[str]) -> dict:
    return {
        "matches": [
            {
                "id": f"match-{index:03d}",
                "segment_id": f"seg-{index:03d}",
                "status": "selected",
                "source_path": path,
                "source_start_ms": (index - 1) * 1000,
                "source_end_ms": index * 1000,
            }
            for index, path in enumerate(paths, start=1)
        ]
    }


def test_edit_diversity_warns_when_most_segments_reuse_one_source_video():
    diagnosis = diagnose_edit_diversity(
        _recipe(5),
        _matches(["assets/mother.mp4"] * 4 + ["assets/detail.mp4"]),
    )

    assert diagnosis["status"] == "warning"
    assert diagnosis["selected_segment_count"] == 5
    assert diagnosis["distinct_source_video_count"] == 2
    assert diagnosis["most_reused_source_count"] == 4
    assert "voiceover shell" in diagnosis["warnings"][0]


def test_edit_diversity_passes_when_selected_segments_use_distinct_sources():
    diagnosis = diagnose_edit_diversity(
        _recipe(5),
        _matches(
            [
                "assets/01-hook.mp4",
                "assets/02-pain.mp4",
                "assets/03-demo.mp4",
                "assets/04-proof.mp4",
                "assets/05-cta.mp4",
            ]
        ),
    )

    assert diagnosis["status"] == "pass"
    assert diagnosis["distinct_source_video_count"] == 5
    assert diagnosis["warnings"] == []
