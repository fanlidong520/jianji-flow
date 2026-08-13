import pytest

from jianji_flow.planner import build_segment_plan, default_beats
from jianji_flow.reference import ReferenceBeat


def test_product_plan_roles_and_bounds():
    segments = build_segment_plan("product", 15000, "Hook line\nFeature line")

    assert [segment["role"] for segment in segments] == ["hook", "pain", "feature", "evidence", "cta"]
    assert segments[0]["start_ms"] == 0
    assert segments[-1]["end_ms"] == 15000
    assert all(segment["end_ms"] > segment["start_ms"] for segment in segments)


def test_talking_head_plan_roles():
    segments = build_segment_plan("talking-head", 45000, None)

    assert [segment["role"] for segment in segments] == [
        "topic",
        "claim",
        "explanation",
        "evidence",
        "conclusion",
    ]


def test_plan_uses_integer_continuous_times():
    segments = build_segment_plan("product", 15001, None)

    assert all(isinstance(segment["start_ms"], int) for segment in segments)
    assert all(isinstance(segment["end_ms"], int) for segment in segments)
    assert [segment["start_ms"] for segment in segments[1:]] == [
        segment["end_ms"] for segment in segments[:-1]
    ]
    assert segments[-1]["end_ms"] == 15001


def test_script_lines_are_used_as_captions_before_role_fallback():
    segments = build_segment_plan("product", 15000, "First caption\nSecond caption")

    assert segments[0]["caption"] == "First caption"
    assert segments[1]["caption"] == "Second caption"
    assert segments[2]["caption"] == "feature"


def test_script_section_headings_are_not_used_as_captions():
    script = "[01 开头吸引]\n清洁死角不用硬擦。\n[02 使用前痛点]\n换对工具更省力。"

    segments = build_segment_plan("product", 15000, script)

    assert segments[0]["caption"] == "清洁死角不用硬擦。"
    assert segments[1]["caption"] == "换对工具更省力。"
    assert all("[" not in segment["caption"] for segment in segments[:2])


def test_default_beats_return_dataclasses():
    beats = default_beats("talking-head", 5000)

    assert all(isinstance(beat, ReferenceBeat) for beat in beats)
    assert beats[0].start_ms == 0
    assert beats[-1].end_ms == 5000


@pytest.mark.parametrize("mode", ["", "bad"])
def test_invalid_mode_fails(mode):
    with pytest.raises(ValueError):
        build_segment_plan(mode, 15000, None)


def test_duration_too_short_for_roles_fails():
    with pytest.raises(ValueError):
        build_segment_plan("product", 4, None)
