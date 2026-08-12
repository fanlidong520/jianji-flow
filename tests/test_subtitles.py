from pathlib import Path

import pytest

from jianji_flow.subtitles import ass_from_recipe, format_srt_time, srt_from_recipe, write_ass, write_srt


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


def test_srt_from_recipe_splits_long_chinese_caption_into_short_blocks():
    recipe = {
        "segments": [
            {
                "start_ms": 0,
                "end_ms": 6000,
                "caption": "家里难清理的地方，其实就那几个，平时不显眼，打扫时最费劲。",
            },
        ]
    }

    srt = srt_from_recipe(recipe)

    assert "\n2\n" in srt
    assert "00:00:06,000" in srt
    caption_lines = [
        line
        for line in srt.splitlines()
        if line and not line.isdigit() and "-->" not in line
    ]
    assert caption_lines
    assert all(len(line) <= 14 for line in caption_lines)


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


def test_ass_from_recipe_contains_chinese_caption_and_style():
    recipe = {
        "target": {"width": 720, "height": 1280, "fps": 30},
        "segments": [{"start_ms": 0, "end_ms": 1200, "caption": "家里难刷角落"}],
    }

    ass = ass_from_recipe(recipe, width=720, height=1280)

    assert "[Script Info]" in ass
    assert "Microsoft YaHei" in ass
    assert "家里难刷角落" in ass


def test_ass_from_recipe_wraps_long_chinese_caption_for_vertical_video():
    recipe = {
        "target": {"width": 592, "height": 1280, "fps": 30},
        "segments": [
            {
                "start_ms": 0,
                "end_ms": 6000,
                "caption": "家里难清理的地方，其实就那几个，平时不显眼，打扫时最费劲。",
            },
        ],
    }

    ass = ass_from_recipe(recipe, width=592, height=1280)

    dialogue_lines = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogue_lines) >= 2
    for line in dialogue_lines:
        text = line.rsplit(",,", 1)[-1]
        for caption_line in text.split("\\N"):
            assert len(caption_line) <= 14


def test_ass_from_recipe_places_vertical_captions_above_platform_ui():
    recipe = {
        "target": {"width": 592, "height": 1280, "fps": 30},
        "segments": [{"start_ms": 0, "end_ms": 1000, "caption": "家居清洁"}],
    }

    ass = ass_from_recipe(recipe, width=592, height=1280)

    style_line = next(line for line in ass.splitlines() if line.startswith("Style: Default"))
    assert style_line.endswith(",230,1")


def test_ass_from_recipe_does_not_double_escape_caption_text():
    recipe = {
        "target": {"width": 592, "height": 1280, "fps": 30},
        "segments": [{"start_ms": 0, "end_ms": 1000, "caption": "这个清洁小工具真的很顺手适合每天用"}],
    }

    ass = ass_from_recipe(recipe, width=592, height=1280)

    dialogue_lines = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    assert dialogue_lines
    assert all("\\\\N" not in line for line in dialogue_lines)


def test_write_ass_creates_utf8_file(tmp_path: Path):
    recipe = {
        "target": {"width": 720, "height": 1280, "fps": 30},
        "segments": [{"start_ms": 0, "end_ms": 1000, "caption": "可伸缩清洁刷"}],
    }
    output = tmp_path / "captions.ass"

    write_ass(recipe, output)

    assert "可伸缩清洁刷" in output.read_text(encoding="utf-8")
