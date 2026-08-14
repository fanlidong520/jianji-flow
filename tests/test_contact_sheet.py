from PIL import Image

from jianji_flow.contact_sheet import (
    build_frame_times_ms,
    build_segment_frame_times_ms,
    build_shot_frame_times_ms,
    write_reference_comparison_sheet,
    write_shot_contact_sheet,
)


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


def test_build_shot_frame_times_ms_uses_final_timeline_shot_midpoints():
    recipe = {
        "segments": [
            {"id": "seg-001", "start_ms": 0, "end_ms": 2000, "match_id": "match-001"},
            {"id": "seg-002", "start_ms": 2000, "end_ms": 5000, "match_id": "match-002"},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "shots": [
                    {"source_start_ms": 0, "source_end_ms": 700},
                    {"source_start_ms": 700, "source_end_ms": 2000},
                ],
            },
            {"id": "match-002"},
        ]
    }

    assert build_shot_frame_times_ms(recipe, matches) == [
        ("seg-001 / shot-01", 350),
        ("seg-001 / shot-02", 1350),
        ("seg-002 / shot-01", 3500),
    ]


def test_build_shot_frame_times_ms_applies_playback_rate():
    recipe = {
        "segments": [{"id": "seg-001", "start_ms": 0, "end_ms": 1000, "match_id": "match-001"}]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "playback_rate": 2.0,
                "shots": [
                    {"source_start_ms": 0, "source_end_ms": 1000},
                    {"source_start_ms": 1000, "source_end_ms": 2000},
                ],
            }
        ]
    }

    assert build_shot_frame_times_ms(recipe, matches) == [
        ("seg-001 / shot-01", 250),
        ("seg-001 / shot-02", 750),
    ]


def test_shot_contact_sheet_contains_labeled_tiles(tmp_path, monkeypatch):
    def fake_extract(_ffmpeg, _video_path, frame_path, _time_ms):
        Image.new("RGB", (100, 200), "#3b82f6").save(frame_path)

    monkeypatch.setattr("jianji_flow.contact_sheet._extract_frame", fake_extract)
    output = tmp_path / "shot-contact-sheet.png"
    recipe = {
        "segments": [{"id": "seg-001", "start_ms": 0, "end_ms": 2000, "match_id": "match-001"}]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "shots": [
                    {"source_start_ms": 0, "source_end_ms": 900},
                    {"source_start_ms": 900, "source_end_ms": 2000},
                ],
            }
        ]
    }

    write_shot_contact_sheet(tmp_path / "remix.mp4", output, recipe=recipe, matches=matches)

    with Image.open(output) as image:
        assert image.width == 4 * (220 + 8) + 8
        assert image.height > 28 + 200


def test_reference_comparison_sheet_contains_two_rows(tmp_path, monkeypatch):
    def fake_write(_video_path, output_path, *, frames=5, recipe=None):
        row = Image.new("RGB", (8 + frames * (220 + 8), 8 + 440 + 8), "white")
        for index in range(frames):
            tile = Image.new("RGB", (220, 440), ((index * 40) % 255, 20, 30))
            row.paste(tile, (8 + index * (220 + 8), 8))
            tile.close()
        row.save(output_path)

    monkeypatch.setattr("jianji_flow.contact_sheet.write_contact_sheet", fake_write)
    output = tmp_path / "reference-comparison.png"
    recipe = {
        "segments": [
            {"id": "seg-001", "start_ms": 0, "end_ms": 1000},
            {"id": "seg-002", "start_ms": 1000, "end_ms": 2000},
        ]
    }

    write_reference_comparison_sheet(
        tmp_path / "reference.mp4",
        tmp_path / "remix.mp4",
        output,
        recipe=recipe,
    )

    with Image.open(output) as image:
        assert image.width == 86 + 2 * (220 + 8) + 8
        assert image.height == 2 * (28 + 440 + 8) + 8
