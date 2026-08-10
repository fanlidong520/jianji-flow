from pathlib import Path

import pytest

from jianji_flow.subtitles import format_srt_time, srt_from_recipe, write_srt


def test_format_srt_time():
    assert format_srt_time(0) == "00:00:00,000"
    assert format_srt_time(3723456) == "01:02:03,456"


def test_format_srt_time_rejects_negative_values():
    with pytest.raises(ValueError):
        format_srt_time(-1)


def test_srt_from_recipe_uses_captions():
    recipe = {
        "segments": [
            {"start_ms": 0, "end_ms": 1200, "caption": "First line"},
            {"start_ms": 1200, "end_ms": 2500, "caption": "Second line"},
        ]
    }

    srt = srt_from_recipe(recipe)

    assert "1\n00:00:00,000 --> 00:00:01,200\nFirst line" in srt
    assert "2\n00:00:01,200 --> 00:00:02,500\nSecond line" in srt
    assert srt.endswith("\n")


def test_srt_from_recipe_rejects_overlapping_segments():
    recipe = {
        "segments": [
            {"start_ms": 0, "end_ms": 1200, "caption": "First line"},
            {"start_ms": 1100, "end_ms": 2500, "caption": "Second line"},
        ]
    }

    with pytest.raises(ValueError, match="overlap"):
        srt_from_recipe(recipe)


def test_srt_from_recipe_skips_empty_captions_but_keeps_numbering():
    recipe = {
        "segments": [
            {"start_ms": 0, "end_ms": 1000, "caption": ""},
            {"start_ms": 1000, "end_ms": 2000, "caption": "Visible"},
        ]
    }

    srt = srt_from_recipe(recipe)

    assert srt.startswith("1\n")
    assert "Visible" in srt
    assert "00:00:00,000" not in srt


def test_write_srt_creates_utf8_file(tmp_path: Path):
    output = tmp_path / "nested" / "captions.srt"
    recipe = {"segments": [{"start_ms": 0, "end_ms": 1000, "caption": "Visible"}]}

    write_srt(recipe, output)

    assert output.read_text(encoding="utf-8").startswith("1\n00:00:00,000")
