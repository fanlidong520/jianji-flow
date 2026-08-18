from pathlib import Path

from PIL import Image

from jianji_flow.visual_similarity import is_visually_similar, mean_frame_difference


def test_mean_frame_difference_detects_identical_frames(tmp_path, monkeypatch):
    left_video = tmp_path / "left.mp4"
    right_video = tmp_path / "right.mp4"
    left_video.write_bytes(b"fake left video")
    right_video.write_bytes(b"fake right video")

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        assert time_ms in {250, 500, 750}
        Image.new("RGB", (80, 80), "#4477aa").save(frame_path)

    monkeypatch.setattr("jianji_flow.visual_similarity._extract_frame", fake_extract_frame)

    score = mean_frame_difference(left_video, right_video, duration_ms=1000, diagnostics_dir=tmp_path / "frames")

    assert score == 0
    assert is_visually_similar(left_video, right_video, duration_ms=1000, diagnostics_dir=tmp_path / "frames")


def test_mean_frame_difference_detects_different_frames(tmp_path, monkeypatch):
    left_video = tmp_path / "left.mp4"
    right_video = tmp_path / "right.mp4"
    left_video.write_bytes(b"fake left video")
    right_video.write_bytes(b"fake right video")

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        color = "#111111" if video_path == left_video else "#eeeeee"
        Image.new("RGB", (80, 80), color).save(frame_path)

    monkeypatch.setattr("jianji_flow.visual_similarity._extract_frame", fake_extract_frame)

    assert mean_frame_difference(left_video, right_video, duration_ms=1000, diagnostics_dir=tmp_path / "frames") > 100
    assert not is_visually_similar(left_video, right_video, duration_ms=1000, diagnostics_dir=tmp_path / "frames")


def test_mean_frame_difference_samples_requested_source_starts(tmp_path, monkeypatch):
    left_video = tmp_path / "left.mp4"
    right_video = tmp_path / "right.mp4"
    left_video.write_bytes(b"fake left video")
    right_video.write_bytes(b"fake right video")
    calls = []

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        calls.append((video_path.name, time_ms))
        Image.new("RGB", (80, 80), "#4477aa").save(frame_path)

    monkeypatch.setattr("jianji_flow.visual_similarity._extract_frame", fake_extract_frame)

    mean_frame_difference(
        left_video,
        right_video,
        duration_ms=1000,
        diagnostics_dir=tmp_path / "frames",
        left_start_ms=2000,
        right_start_ms=1000,
    )

    assert calls == [
        ("left.mp4", 2250),
        ("right.mp4", 1250),
        ("left.mp4", 2500),
        ("right.mp4", 1500),
        ("left.mp4", 2750),
        ("right.mp4", 1750),
    ]


def test_mean_frame_difference_keeps_diagnostics_for_same_stem_paths(tmp_path, monkeypatch):
    left_video = tmp_path / "left" / "clip.mp4"
    right_video = tmp_path / "right" / "clip.mp4"
    left_video.parent.mkdir()
    right_video.parent.mkdir()
    left_video.write_bytes(b"fake left video")
    right_video.write_bytes(b"fake right video")

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        Image.new("RGB", (80, 80), "#4477aa").save(frame_path)

    monkeypatch.setattr("jianji_flow.visual_similarity._extract_frame", fake_extract_frame)

    mean_frame_difference(left_video, right_video, duration_ms=1000, diagnostics_dir=tmp_path / "frames")

    assert len(list((tmp_path / "frames").glob("*.png"))) == 6


def test_mean_frame_difference_reuses_existing_diagnostic_frames(tmp_path, monkeypatch):
    left_video = tmp_path / "left.mp4"
    right_video = tmp_path / "right.mp4"
    left_video.write_bytes(b"fake left video")
    right_video.write_bytes(b"fake right video")
    calls = []

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        calls.append((video_path.name, time_ms))
        Image.new("RGB", (80, 80), "#4477aa").save(frame_path)

    monkeypatch.setattr("jianji_flow.visual_similarity._extract_frame", fake_extract_frame)

    for _ in range(2):
        mean_frame_difference(left_video, right_video, duration_ms=1000, diagnostics_dir=tmp_path / "frames")

    assert len(calls) == 6


def test_mean_frame_difference_requires_positive_duration(tmp_path):
    try:
        mean_frame_difference(tmp_path / "left.mp4", tmp_path / "right.mp4", duration_ms=0, diagnostics_dir=tmp_path)
    except ValueError as exc:
        assert "duration_ms" in str(exc)
    else:
        raise AssertionError("zero duration should fail")
