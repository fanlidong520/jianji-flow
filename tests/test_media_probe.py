from pathlib import Path
import subprocess

import pytest

from jianji_flow.media_probe import (
    MediaInfo,
    parse_ffprobe_json,
    run_ffprobe,
)


def _payload(*, audio=True, duration="12.345", frame_rate="30/1", rotation=None):
    video = {
        "codec_type": "video",
        "width": 1920,
        "height": 1080,
        "avg_frame_rate": frame_rate,
    }
    if rotation is not None:
        video["tags"] = {"rotate": str(rotation)}
    streams = [video]
    if audio:
        streams.append({"codec_type": "audio"})
    return {"format": {"duration": duration}, "streams": streams}


def test_parse_video_with_audio():
    info = parse_ffprobe_json(_payload(), "clip.mp4")

    assert info == MediaInfo(
        source_path="clip.mp4",
        duration_ms=12345,
        width=1920,
        height=1080,
        fps=30.0,
        has_audio=True,
        rotation=0,
    )


def test_parse_video_without_audio():
    assert parse_ffprobe_json(_payload(audio=False), "silent.mp4").has_audio is False


def test_missing_video_stream_raises_value_error():
    with pytest.raises(ValueError, match="video stream"):
        parse_ffprobe_json({"format": {"duration": "1"}, "streams": [{"codec_type": "audio"}]}, "audio.mp3")


@pytest.mark.parametrize(
    ("duration", "expected_ms"),
    [("1.2349", 1235), ("0", 0), ("2.0", 2000)],
)
def test_duration_is_rounded_to_integer_milliseconds(duration, expected_ms):
    assert parse_ffprobe_json(_payload(duration=duration), "clip.mp4").duration_ms == expected_ms


@pytest.mark.parametrize(
    ("frame_rate", "expected_fps"),
    [("30/1", 30.0), ("30000/1001", 30000 / 1001), ("0/0", 0.0)],
)
def test_average_frame_rate_is_parsed(frame_rate, expected_fps):
    assert parse_ffprobe_json(_payload(frame_rate=frame_rate), "clip.mp4").fps == pytest.approx(expected_fps)


def test_rotation_metadata_is_preserved():
    assert parse_ffprobe_json(_payload(rotation=90), "rotated.mp4").rotation == 90


def test_run_ffprobe_uses_json_output(monkeypatch):
    completed = subprocess.CompletedProcess([], 0, '{"format":{"duration":"1"},"streams":[{"codec_type":"video","width":1,"height":2,"avg_frame_rate":"30/1"}]}', "")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)

    info = run_ffprobe(Path("clip.mp4"), timeout_s=7)

    assert info.duration_ms == 1000


def test_run_ffprobe_uses_safe_subprocess_arguments(monkeypatch):
    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess([], 0, '{"format":{"duration":"1"},"streams":[{"codec_type":"video","width":1,"height":2,"avg_frame_rate":"30/1"}]}', "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_ffprobe(Path("clip.mp4"), timeout_s=7)

    command = captured["args"][0]
    assert isinstance(command, list)
    assert command[0] == "ffprobe"
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["timeout"] == 7
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["encoding"] == "utf-8"


def test_run_ffprobe_reports_subprocess_failure(monkeypatch):
    completed = subprocess.CompletedProcess([], 1, "", "decoder exploded")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)

    with pytest.raises(RuntimeError, match="ffprobe failed.*decoder exploded"):
        run_ffprobe(Path("clip.mp4"))


def test_run_ffprobe_reports_non_json_output(monkeypatch):
    completed = subprocess.CompletedProcess([], 0, "not json", "")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)

    with pytest.raises(ValueError, match="invalid JSON"):
        run_ffprobe(Path("clip.mp4"))
