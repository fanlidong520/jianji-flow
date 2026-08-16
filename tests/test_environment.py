from pathlib import Path

from jianji_flow.environment import check_environment, format_environment_report


def test_check_environment_reports_core_tool_statuses(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "ffmpeg ok", "ffprobe": "ffprobe ok"},
    )
    monkeypatch.setattr("jianji_flow.environment.platform.system", lambda: "Windows")
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: True)

    report = check_environment(output_root=tmp_path)

    assert report["status"] == "pass"
    assert report["checks"]["ffmpeg"]["status"] == "pass"
    assert report["checks"]["ffprobe"]["status"] == "pass"
    assert report["checks"]["local_tts"]["status"] == "pass"
    assert report["checks"]["writable_output"]["status"] == "pass"


def test_check_environment_reports_missing_tts_without_crashing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "ffmpeg ok", "ffprobe": "ffprobe ok"},
    )
    monkeypatch.setattr("jianji_flow.environment.platform.system", lambda: "Windows")
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: False)

    report = check_environment(output_root=tmp_path)

    assert report["status"] == "fail"
    assert report["checks"]["local_tts"]["status"] == "fail"
    assert "Chinese TTS" in report["checks"]["local_tts"]["message"]
    assert "--voiceover" in format_environment_report(report)


def test_check_environment_reports_missing_ffmpeg_tools(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "missing", "ffprobe": ""},
    )
    monkeypatch.setattr("jianji_flow.environment.platform.system", lambda: "Windows")
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: True)

    report = check_environment(output_root=tmp_path)

    assert report["status"] == "fail"
    assert report["checks"]["ffmpeg"]["status"] == "fail"
    assert report["checks"]["ffprobe"]["status"] == "fail"
    text = format_environment_report(report)
    assert "winget install Gyan.FFmpeg" in text
    assert "Run this command again" in text


def test_check_environment_explains_non_windows_tts_requirement(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "ffmpeg ok", "ffprobe": "ffprobe ok"},
    )
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: False)
    monkeypatch.setattr("jianji_flow.environment.platform.system", lambda: "Linux")

    report = check_environment(output_root=tmp_path)

    assert report["status"] == "fail"
    assert "requires Windows" in report["checks"]["local_tts"]["message"]


def test_check_environment_reports_unwritable_output_path(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "ffmpeg ok", "ffprobe": "ffprobe ok"},
    )
    monkeypatch.setattr("jianji_flow.environment.platform.system", lambda: "Windows")
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: True)
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("already a file", encoding="utf-8")

    report = check_environment(output_root=file_path)

    assert report["status"] == "fail"
    assert report["checks"]["writable_output"]["status"] == "fail"


def test_check_environment_does_not_overwrite_existing_probe_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "ffmpeg ok", "ffprobe": "ffprobe ok"},
    )
    monkeypatch.setattr("jianji_flow.environment.platform.system", lambda: "Windows")
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: True)
    existing = tmp_path / ".jianji-flow-write-test"
    existing.write_text("user data", encoding="utf-8")

    report = check_environment(output_root=tmp_path)

    assert report["status"] == "pass"
    assert existing.read_text(encoding="utf-8") == "user data"


def test_format_environment_report_ends_with_plain_decision(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "ffmpeg ok", "ffprobe": "ffprobe ok"},
    )
    monkeypatch.setattr("jianji_flow.environment.platform.system", lambda: "Windows")
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: True)

    text = format_environment_report(check_environment(output_root=tmp_path))

    assert "Environment" in text
    assert text.strip().endswith("Ready to run quick draft")
