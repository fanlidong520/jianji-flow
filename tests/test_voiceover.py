import base64
import math
import subprocess
import struct
import wave
from pathlib import Path

import pytest

from jianji_flow.voiceover import (
    build_voiceover_text,
    create_voiceover,
    create_edge_voiceover,
    has_edge_tts,
    has_local_chinese_tts,
    probe_voiceover,
    validate_voiceover,
)


def _write_tone_wav(path: Path, *, seconds: float = 0.25) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    frame_count = int(sample_rate * seconds)
    frames = bytearray()
    for index in range(frame_count):
        value = int(math.sin(index / sample_rate * 440 * math.tau) * 8000)
        frames.extend(struct.pack("<h", value))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))


def _write_silent_wav(path: Path, *, seconds: float = 0.25) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    frame_count = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\0\0" * frame_count)


def _write_single_pulse_wav(path: Path, *, seconds: float = 0.5) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    frame_count = int(sample_rate * seconds)
    frames = bytearray(b"\0\0" * frame_count)
    frames[0:2] = struct.pack("<h", 12000)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))


def test_build_voiceover_text_joins_non_empty_segment_captions():
    recipe = {
        "segments": [
            {"caption": "\u7b2c\u4e00\u53e5"},
            {"caption": "  "},
            {"caption": "\u7b2c\u4e8c\u53e5"},
        ]
    }

    assert build_voiceover_text(recipe) == "\u7b2c\u4e00\u53e5\n\u7b2c\u4e8c\u53e5"


def test_build_voiceover_text_rejects_empty_script():
    with pytest.raises(ValueError, match="voiceover text"):
        build_voiceover_text({"segments": [{"caption": ""}]})


def test_validate_voiceover_rejects_missing_empty_invalid_or_silent_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_voiceover(tmp_path / "missing.wav")

    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        validate_voiceover(empty)

    fake = tmp_path / "fake.wav"
    fake.write_bytes(b"RIFFfake-wave-data")
    with pytest.raises(ValueError, match="decode"):
        validate_voiceover(fake)

    silent = tmp_path / "silent.wav"
    _write_silent_wav(silent)
    with pytest.raises(ValueError, match="silent"):
        validate_voiceover(silent)

    pulse = tmp_path / "pulse.wav"
    _write_single_pulse_wav(pulse)
    with pytest.raises(ValueError, match="silent"):
        validate_voiceover(pulse)


def test_validate_voiceover_rejects_audio_that_is_too_short_for_recipe(tmp_path: Path):
    output = tmp_path / "voiceover.wav"
    _write_tone_wav(output, seconds=0.1)

    with pytest.raises(ValueError, match="too short"):
        validate_voiceover(output, expected_duration_ms=43_933)


def test_validate_voiceover_rejects_audio_that_would_be_truncated(tmp_path: Path):
    output = tmp_path / "voiceover.wav"
    _write_tone_wav(output, seconds=1.1)

    with pytest.raises(ValueError, match="exceeds"):
        validate_voiceover(output, expected_duration_ms=1000)


def test_probe_voiceover_reports_duration_for_decodable_wav(tmp_path: Path):
    output = tmp_path / "voiceover.wav"
    _write_tone_wav(output, seconds=0.5)

    info = probe_voiceover(output)

    assert 450 <= info.duration_ms <= 550


def test_has_local_chinese_tts_returns_false_when_powershell_is_missing(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("powershell")

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", fake_run)

    assert has_local_chinese_tts() is False


def test_has_local_chinese_tts_returns_false_when_powershell_times_out(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", fake_run)

    assert has_local_chinese_tts() is False


def test_has_local_chinese_tts_returns_false_when_powershell_cannot_start(monkeypatch):
    def fake_run(*args, **kwargs):
        raise PermissionError("blocked")

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", fake_run)

    assert has_local_chinese_tts() is False


def test_has_local_chinese_tts_returns_true_when_local_voice_exists(monkeypatch):
    class Result:
        returncode = 0

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", lambda *args, **kwargs: Result())

    assert has_local_chinese_tts() is True


def test_has_local_chinese_tts_checks_voice_selection(monkeypatch):
    captured = {}

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        captured["script"] = base64.b64decode(command[-1]).decode("utf-16le")
        return Result()

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", fake_run)

    assert has_local_chinese_tts() is True
    assert "$s.SelectVoice($voice.VoiceInfo.Name)" in captured["script"]


def test_has_edge_tts_checks_executable_version(monkeypatch):
    calls = []

    class Result:
        returncode = 0

    monkeypatch.setattr("jianji_flow.voiceover.shutil.which", lambda name: "edge-tts.exe")

    def fake_run(command, **kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", fake_run)

    assert has_edge_tts() is True
    assert calls == [["edge-tts.exe", "--version"]]


def test_create_edge_voiceover_converts_generated_media_to_wav(tmp_path: Path, monkeypatch):
    output = tmp_path / "voiceover.wav"
    real_run = subprocess.run
    commands = []

    monkeypatch.setattr("jianji_flow.voiceover.shutil.which", lambda name: "edge-tts.exe")

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] == "edge-tts.exe":
            media_path = Path(command[command.index("--write-media") + 1])
            _write_tone_wav(media_path)

            class Result:
                returncode = 0
                stderr = ""
                stdout = ""

            return Result()
        if command[0] == "ffmpeg":
            _write_tone_wav(Path(command[-1]))

            class Result:
                returncode = 0
                stderr = ""
                stdout = ""

            return Result()
        return real_run(command, **kwargs)

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", fake_run)

    result = create_edge_voiceover({"segments": [{"caption": "家居清洁"}]}, output)

    assert result == output
    assert output.exists()
    assert commands[0][:2] == ["edge-tts.exe", "--voice"]
    assert commands[1][0] == "ffmpeg"
    assert probe_voiceover(output).duration_ms > 0


def test_create_voiceover_invokes_local_tts_and_validates_output(tmp_path: Path, monkeypatch):
    output = tmp_path / "voiceover.wav"
    real_run = subprocess.run

    def fake_run(command, **kwargs):
        if command[:3] != ["powershell", "-NoProfile", "-EncodedCommand"]:
            return real_run(command, **kwargs)
        _write_tone_wav(output)

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        return Result()

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", fake_run)

    result = create_voiceover({"segments": [{"caption": "\u5bb6\u5c45\u6e05\u6d01"}]}, output)

    assert result == output
    assert probe_voiceover(output).duration_ms > 0


def test_create_voiceover_allows_shorter_audio_before_timeline_retime(tmp_path: Path, monkeypatch):
    output = tmp_path / "voiceover.wav"
    real_run = subprocess.run

    def fake_run(command, **kwargs):
        if command[:3] != ["powershell", "-NoProfile", "-EncodedCommand"]:
            return real_run(command, **kwargs)
        _write_tone_wav(output, seconds=0.25)

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        return Result()

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", fake_run)

    result = create_voiceover(
        {
            "duration_ms": 43_933,
            "segments": [{"caption": "\u5bb6\u5c45\u6e05\u6d01"}],
        },
        output,
    )

    assert result == output
    assert probe_voiceover(output).duration_ms < 43_933
