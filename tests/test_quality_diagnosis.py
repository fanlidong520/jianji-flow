from pathlib import Path

from PIL import Image, ImageDraw

from jianji_flow.quality_diagnosis import (
    build_source_frame_times_ms,
    diagnose_contact_sheet_segments,
    diagnose_frame,
    diagnose_image,
    diagnose_source_matches,
)


def test_diagnose_frame_warns_when_lower_band_has_dense_overlay_text():
    image = Image.new("RGB", (592, 1280), "#c8d8d0")
    draw = ImageDraw.Draw(image)
    for row in range(6):
        y = 1010 + row * 28
        for col in range(18):
            x = 24 + col * 30
            draw.rectangle((x, y, x + 18, y + 9), fill="white")
    for col in range(5):
        x = 110 + col * 90
        draw.ellipse((x, 1180, x + 30, 1210), outline="white", width=4)

    result = diagnose_frame(image)

    assert result["status"] == "warning"
    assert result["severity"] == "warning"
    assert any("platform UI" in warning for warning in result["warnings"])


def test_diagnose_frame_warns_when_top_and_bottom_platform_chrome_are_present():
    image = Image.new("RGB", (592, 1280), "#c8d8d0")
    draw = ImageDraw.Draw(image)
    for column in range(10):
        x = 30 + column * 52
        draw.rectangle((x, 30, x + 18, 42), fill="white")
    draw.rectangle((0, 1050, 592, 1279), fill="#111111")
    for column in range(6):
        x = 70 + column * 90
        draw.ellipse((x, 1130, x + 28, 1158), outline="white", width=4)

    result = diagnose_frame(image)

    assert result["status"] == "warning"
    assert any("upper" in warning or "platform UI" in warning for warning in result["warnings"])


def test_diagnose_frame_allows_clean_visual_frame():
    image = Image.new("RGB", (592, 1280), "#c8d8d0")
    draw = ImageDraw.Draw(image)
    draw.rectangle((170, 420, 420, 760), fill="#557a95")

    result = diagnose_frame(image)

    assert result["status"] == "pass"
    assert result["severity"] == "pass"
    assert result["warnings"] == []


def test_diagnose_frame_allows_large_bright_product_area_in_lower_band():
    image = Image.new("RGB", (592, 1280), "#c8d8d0")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 880, 540, 1250), fill="#f8f8f2")
    draw.rectangle((110, 960, 480, 1030), fill="#76a98f")

    result = diagnose_frame(image)

    assert result["status"] == "pass"
    assert result["severity"] == "pass"
    assert result["warnings"] == []


def test_diagnose_frame_fails_when_lower_band_residue_is_severe():
    image = Image.new("RGB", (592, 1280), "#c8d8d0")
    draw = ImageDraw.Draw(image)
    for row in range(18):
        y = 890 + row * 18
        for col in range(24):
            x = 12 + col * 24
            draw.rectangle((x, y, x + 16, y + 8), fill="white")

    result = diagnose_frame(image)

    assert result["status"] == "fail"
    assert result["severity"] == "fail"
    assert any("severe" in warning for warning in result["warnings"])


def test_diagnose_image_reads_local_image(tmp_path: Path):
    image_path = tmp_path / "frame.png"
    Image.new("RGB", (320, 180), "#ffffff").save(image_path)

    result = diagnose_image(image_path)

    assert result["status"] == "pass"
    assert result["source"] == image_path.as_posix()


def test_diagnose_contact_sheet_segments_reports_specific_segment(tmp_path: Path):
    contact_sheet = tmp_path / "contact-sheet.png"
    clean = Image.new("RGB", (220, 400), "#c8d8d0")
    risky = Image.new("RGB", (220, 400), "#c8d8d0")
    draw = ImageDraw.Draw(risky)
    for row in range(4):
        y = 308 + row * 18
        for col in range(9):
            x = 12 + col * 22
            draw.rectangle((x, y, x + 12, y + 6), fill="white")
    sheet = Image.new("RGB", (456, 416), "white")
    sheet.paste(clean, (8, 8))
    sheet.paste(risky, (236, 8))
    sheet.save(contact_sheet)
    recipe = {
        "segments": [
            {"id": "seg-001", "start_ms": 0, "end_ms": 1000},
            {"id": "seg-002", "start_ms": 1000, "end_ms": 2000},
        ]
    }

    result = diagnose_contact_sheet_segments(contact_sheet, recipe)

    assert result["status"] == "warning"
    assert result["failures"] == []
    assert result["warnings"] == [
        "seg-002: possible platform UI or original subtitles in the lower safe area; captions may overlap."
    ]


def test_diagnose_contact_sheet_segments_reports_severe_residue_as_failure(tmp_path: Path):
    contact_sheet = tmp_path / "contact-sheet.png"
    severe = Image.new("RGB", (220, 400), "#c8d8d0")
    draw = ImageDraw.Draw(severe)
    for row in range(10):
        y = 292 + row * 10
        for col in range(12):
            x = 8 + col * 17
            draw.rectangle((x, y, x + 12, y + 5), fill="white")
    sheet = Image.new("RGB", (236, 416), "white")
    sheet.paste(severe, (8, 8))
    sheet.save(contact_sheet)
    recipe = {"segments": [{"id": "seg-001", "start_ms": 0, "end_ms": 1000}]}

    result = diagnose_contact_sheet_segments(contact_sheet, recipe)

    assert result["status"] == "fail"
    assert result["warnings"] == []
    assert result["failures"] == [
        "seg-001: severe platform UI or original subtitles in the lower safe area; replace or crop this source clip."
    ]


def test_build_source_frame_times_samples_inside_source_range():
    assert build_source_frame_times_ms(1000, 5000, samples=3) == [2000, 3000, 4000]


def test_diagnose_source_matches_reports_preflight_failures(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake video; extraction is monkeypatched")

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        image = Image.new("RGB", (592, 1280), "#c8d8d0")
        draw = ImageDraw.Draw(image)
        if time_ms == 3000:
            for row in range(18):
                y = 560 + row * 10
                for col in range(24):
                    x = 12 + col * 18
                    draw.rectangle((x, y, x + 12, y + 6), fill="white")
        image.save(frame_path)

    monkeypatch.setattr("jianji_flow.quality_diagnosis._extract_frame", fake_extract_frame)
    recipe = {"segments": [{"id": "seg-001", "match_id": "match-001"}]}
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "source_path": source.as_posix(),
                "source_start_ms": 1000,
                "source_end_ms": 5000,
            }
        ]
    }

    result = diagnose_source_matches(recipe, matches, tmp_path / "source-diagnostics", samples_per_segment=3)

    assert result["status"] == "fail"
    assert result["warnings"] == []
    assert result["diagnostics_dir"] == (tmp_path / "source-diagnostics").as_posix()
    assert any("seg-001 source frame 2" in failure for failure in result["failures"])
    assert (tmp_path / "source-diagnostics" / "seg-001-02.png").exists()


def test_diagnose_source_matches_escalates_repeated_warnings_before_rendering(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake video; extraction is monkeypatched")

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        Image.new("RGB", (592, 1280), "#c8d8d0").save(frame_path)

    monkeypatch.setattr("jianji_flow.quality_diagnosis._extract_frame", fake_extract_frame)
    monkeypatch.setattr(
        "jianji_flow.quality_diagnosis.diagnose_image",
        lambda path: {
            "severity": "warning",
            "warnings": ["possible platform UI or original subtitles"],
            "metrics": {},
        },
    )
    recipe = {
        "segments": [
            {"id": "seg-001", "match_id": "match-001"},
            {"id": "seg-002", "match_id": "match-002"},
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "source_path": source.as_posix(),
                "source_start_ms": 0,
                "source_end_ms": 3000,
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "status": "selected",
                "source_path": source.as_posix(),
                "source_start_ms": 0,
                "source_end_ms": 3000,
            },
        ]
    }

    result = diagnose_source_matches(recipe, matches, tmp_path / "source-diagnostics", samples_per_segment=1)

    assert result["status"] == "fail"
    assert any("Repeated platform UI/original-subtitle warnings" in failure for failure in result["failures"])
    assert "seg-001" in result["failures"][0]
    assert "seg-002" in result["failures"][0]


def test_diagnose_source_matches_keeps_one_warning_reviewable(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake video; extraction is monkeypatched")

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        Image.new("RGB", (592, 1280), "#c8d8d0").save(frame_path)

    monkeypatch.setattr("jianji_flow.quality_diagnosis._extract_frame", fake_extract_frame)
    monkeypatch.setattr(
        "jianji_flow.quality_diagnosis.diagnose_image",
        lambda path: {
            "severity": "warning",
            "warnings": ["possible platform UI or original subtitles"],
            "metrics": {},
        },
    )
    recipe = {"segments": [{"id": "seg-001", "match_id": "match-001"}]}
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "source_path": source.as_posix(),
                "source_start_ms": 0,
                "source_end_ms": 3000,
            }
        ]
    }

    result = diagnose_source_matches(recipe, matches, tmp_path / "source-diagnostics", samples_per_segment=1)

    assert result["status"] == "warning"
    assert result["failures"] == []
    assert result["warnings"]


def test_diagnose_source_matches_removes_clean_diagnostics_by_default(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake video; extraction is monkeypatched")

    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        Image.new("RGB", (592, 1280), "#c8d8d0").save(frame_path)

    monkeypatch.setattr("jianji_flow.quality_diagnosis._extract_frame", fake_extract_frame)
    recipe = {"segments": [{"id": "seg-001", "match_id": "match-001"}]}
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "source_path": source.as_posix(),
                "source_start_ms": 0,
                "source_end_ms": 3000,
            }
        ]
    }

    result = diagnose_source_matches(recipe, matches, tmp_path / "source-diagnostics", samples_per_segment=2)

    assert result["status"] == "pass"
    assert result["failures"] == []
    assert result["warnings"] == []
    assert result["clean_segment_ids"] == ["seg-001"]
    assert not (tmp_path / "source-diagnostics").exists()
