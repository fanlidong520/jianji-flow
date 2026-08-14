from PIL import Image

from jianji_flow.contact_sheet import (
    build_frame_times_ms,
    build_segment_frame_times_ms,
    write_reference_comparison_sheet,
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
