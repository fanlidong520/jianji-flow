from pathlib import Path

import pytest

from jianji_flow.voiceover import build_voiceover_text, create_voiceover, validate_voiceover


def test_build_voiceover_text_joins_non_empty_segment_captions():
    recipe = {
        "segments": [
            {"caption": "第一句"},
            {"caption": "  "},
            {"caption": "第二句"},
        ]
    }

    assert build_voiceover_text(recipe) == "第一句\n第二句"


def test_build_voiceover_text_rejects_empty_script():
    with pytest.raises(ValueError, match="voiceover text"):
        build_voiceover_text({"segments": [{"caption": ""}]})


def test_validate_voiceover_rejects_missing_or_empty_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_voiceover(tmp_path / "missing.wav")

    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        validate_voiceover(empty)


def test_create_voiceover_invokes_local_tts_and_validates_output(tmp_path: Path, monkeypatch):
    output = tmp_path / "voiceover.wav"

    def fake_run(command, check, capture_output, text, encoding, errors):
        assert command[0] == "powershell"
        assert str(output) in " ".join(command)
        output.write_bytes(b"RIFFfake-wave-data")

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        return Result()

    monkeypatch.setattr("jianji_flow.voiceover.subprocess.run", fake_run)

    result = create_voiceover({"segments": [{"caption": "家居清洁"}]}, output)

    assert result == output
    assert output.read_bytes().startswith(b"RIFF")
