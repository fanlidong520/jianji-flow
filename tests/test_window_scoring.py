from pathlib import Path

from PIL import Image

from jianji_flow.window_scoring import score_frame_information, score_source_window


def test_score_frame_information_prefers_detailed_frames():
    flat = Image.new("RGB", (80, 80), "#888888")
    detailed = Image.new("RGB", (80, 80), "#888888")
    pixels = detailed.load()
    for y in range(detailed.height):
        for x in range(detailed.width):
            pixels[x, y] = (20, 20, 20) if (x + y) % 2 else (235, 235, 235)

    assert score_frame_information(detailed) > score_frame_information(flat)


def test_score_source_window_samples_midpoint(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake video; extraction is monkeypatched")

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        assert video_path == source
        assert time_ms == 3000
        Image.new("RGB", (80, 80), "#888888").save(frame_path)

    monkeypatch.setattr("jianji_flow.window_scoring._extract_frame", fake_extract_frame)

    score = score_source_window(source, 2000, 4000, tmp_path / "frames")

    assert score >= 0
    assert (tmp_path / "frames" / "clip-2000-4000.png").exists()
