from jianji_flow.contact_sheet import build_frame_times_ms, build_segment_frame_times_ms


def test_build_frame_times_ms_spreads_frames_across_duration():
    assert build_frame_times_ms(10_000, frames=5) == [1000, 3000, 5000, 7000, 9000]


def test_build_segment_frame_times_ms_uses_each_segment_midpoint():
    recipe = {
        "segments": [
            {"id": "seg-001", "start_ms": 0, "end_ms": 6590},
            {"id": "seg-002", "start_ms": 6590, "end_ms": 15377},
            {"id": "seg-003", "start_ms": 15377, "end_ms": 26360},
            {"id": "seg-004", "start_ms": 26360, "end_ms": 37343},
            {"id": "seg-005", "start_ms": 37343, "end_ms": 43933},
        ]
    }

    assert build_segment_frame_times_ms(recipe) == [3295, 10984, 20868, 31852, 40638]
