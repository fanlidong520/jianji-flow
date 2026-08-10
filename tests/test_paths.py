from pathlib import Path

import pytest

from jianji_flow.paths import (
    ensure_inside,
    make_output_dir,
    reject_url_or_protocol,
    resolve_existing_dir,
    resolve_existing_file,
)


def test_resolve_existing_file_supports_chinese_path_with_spaces(tmp_path: Path):
    file_path = tmp_path / "素材 文件" / "中文片段.mp4"
    file_path.parent.mkdir()
    file_path.write_bytes(b"")

    assert resolve_existing_file(str(file_path)) == file_path.resolve()


def test_resolve_existing_file_raises_for_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        resolve_existing_file(str(tmp_path / "missing.mp4"))


def test_resolve_existing_dir_returns_resolved_directory(tmp_path: Path):
    directory = tmp_path / "素材 文件"
    directory.mkdir()

    assert resolve_existing_dir(str(directory)) == directory.resolve()


def test_ensure_inside_rejects_parent_escape(tmp_path: Path):
    with pytest.raises(ValueError):
        ensure_inside(tmp_path, tmp_path / ".." / "outside")


def test_make_output_dir_rejects_absolute_child_name(tmp_path: Path):
    with pytest.raises(ValueError):
        make_output_dir(tmp_path, str((tmp_path / "elsewhere").resolve()))


def test_reject_url_or_protocol_rejects_url_and_protocol():
    for path_text in (
        "https://example.com/video.mp4",
        "file://video.mp4",
        "file:/tmp/video.mp4",
        "file:\\tmp\\video.mp4",
        "http:/example.com/video.mp4",
        "s3:/bucket/video.mp4",
        "s3:bucket/video.mp4",
        "mailto:clip.mp4",
        "data:text/plain,hello",
        " https://example.com/video.mp4",
        "\tfile:/tmp/video.mp4",
        "//example.com/video.mp4",
        "\\\\server\\share\\video.mp4",
    ):
        with pytest.raises(ValueError):
            reject_url_or_protocol(path_text)


def test_reject_url_or_protocol_allows_windows_drive_paths():
    reject_url_or_protocol("C:\\Users\\me\\clip.mp4")
    reject_url_or_protocol("C:/Users/me/clip.mp4")
