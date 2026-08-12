from pathlib import Path

from PIL import Image, ImageDraw

from jianji_flow.quality_diagnosis import diagnose_contact_sheet_segments, diagnose_frame, diagnose_image


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
    assert any("platform UI" in warning for warning in result["warnings"])


def test_diagnose_frame_allows_clean_visual_frame():
    image = Image.new("RGB", (592, 1280), "#c8d8d0")
    draw = ImageDraw.Draw(image)
    draw.rectangle((170, 420, 420, 760), fill="#557a95")

    result = diagnose_frame(image)

    assert result["status"] == "pass"
    assert result["warnings"] == []


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
    assert result["warnings"] == [
        "seg-002: possible platform UI or original subtitles in the lower safe area; captions may overlap."
    ]
