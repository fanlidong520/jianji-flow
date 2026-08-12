from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


VIDEO_SIZE = "320x180"
VIDEO_WIDTH = 320
VIDEO_HEIGHT = 180
FRAME_RATE = 12
CREATION_TIME = "1970-01-01T00:00:00Z"

SUBLINES = {
    "reference-product": "Structure source only",
    "product-overview": "Hero shot / workflow view",
    "product-detail": "Detail shot / proof moment",
    "reference-talking": "Rhythm source only",
    "talking-wide": "Wide talking-head frame",
    "talking-detail": "Close-up evidence frame",
}


SCENARIOS = {
    "scenario-a-product": {
        "text_name": "script.txt",
        "text": (
            "Hook.\n"
            "Pain.\n"
            "Feature.\n"
            "Proof.\n"
            "Buy.\n"
        ),
        "reference": ("reference-product", "0x6cc6ff", 440, 8.0),
        "assets": [
            ("product-overview", "0x2d8a6e", 520, 3.0),
            ("product-detail", "0xffb347", 660, 3.0),
        ],
    },
    "scenario-b-talking": {
        "text_name": "transcript.txt",
        "text": (
            "Topic.\n"
            "Claim.\n"
            "Explain.\n"
            "Proof.\n"
            "Done.\n"
        ),
        "reference": ("reference-talking", "0xff8a65", 330, 8.0),
        "assets": [
            ("talking-wide", "0x7654d6", 390, 3.0),
            ("talking-detail", "0x42a5f5", 730, 3.0),
        ],
    },
}


def _pil_color(color: str) -> str:
    return "#" + color.removeprefix("0x")


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _draw_centered(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.ImageFont, fill: str) -> None:
    width, _ = _text_size(draw, text, font)
    draw.text(((VIDEO_WIDTH - width) / 2, y), text, font=font, fill=fill)


def _make_frame(path: Path, label: str, color: str) -> None:
    title = label.replace("-", " ").upper()
    subline = SUBLINES.get(label, "Synthetic local media")
    image = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), _pil_color(color))
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, VIDEO_WIDTH, VIDEO_HEIGHT), outline="#111111", width=3)
    draw.rectangle((0, 0, VIDEO_WIDTH, 34), fill="#111111")
    draw.rectangle((18, 54, 302, 138), outline="#ffffff", width=2)
    draw.ellipse((228, 46, 286, 104), fill="#ffffff", outline="#111111", width=2)
    draw.rectangle((36, 94, 170, 122), fill="#ffffff")
    draw.line((40, 145, 280, 145), fill="#111111", width=3)
    draw.line((40, 154, 220, 154), fill="#111111", width=2)

    _draw_centered(draw, 9, title, _font(18, bold=True), "#ffffff")
    _draw_centered(draw, 64, subline, _font(14), "#111111")
    _draw_centered(draw, 101, "VISIBLE SYNTHETIC ASSET", _font(13, bold=True), "#111111")
    image.save(path)


def _make_video(output: Path, label: str, color: str, frequency: int, duration: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to generate synthetic fixtures")

    frame_path = output.with_name(f".{output.stem}.{os.getpid()}.frame.png")
    temp_output = output.with_name(f".{output.stem}.{os.getpid()}.tmp{output.suffix}")
    _make_frame(frame_path, label, color)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(FRAME_RATE),
        "-i",
        str(frame_path),
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={frequency}:sample_rate=8000:duration={duration}",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-t",
        str(duration),
        "-map_metadata",
        "-1",
        "-metadata",
        f"title={label}",
        "-metadata",
        f"creation_time={CREATION_TIME}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "35",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FRAME_RATE),
        "-g",
        str(FRAME_RATE),
        "-bf",
        "0",
        "-c:a",
        "aac",
        "-b:a",
        "32k",
        "-ar",
        "8000",
        "-ac",
        "1",
        "-movflags",
        "+faststart",
        str(temp_output),
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            detail = result.stderr.strip() or "no diagnostic output"
            raise RuntimeError(f"ffmpeg failed for {output}: {detail}")
        temp_output.replace(output)
    finally:
        if frame_path.exists():
            frame_path.unlink()
        if temp_output.exists():
            temp_output.unlink()


def generate_fixtures(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for scenario_name, scenario in SCENARIOS.items():
        scenario_dir = output / scenario_name
        assets_dir = scenario_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        (scenario_dir / scenario["text_name"]).write_text(scenario["text"], encoding="utf-8")

        reference_label, reference_color, reference_frequency, reference_duration = scenario["reference"]
        _make_video(
            scenario_dir / "reference.mp4",
            reference_label,
            reference_color,
            reference_frequency,
            reference_duration,
        )
        for label, color, frequency, duration in scenario["assets"]:
            _make_video(assets_dir / f"{label}.mp4", label, color, frequency, duration)

    malformed_dir = output / "malformed"
    malformed_dir.mkdir(parents=True, exist_ok=True)
    (malformed_dir / "damaged.mp4").write_bytes(b"synthetic fixture is intentionally damaged\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic local synthetic jianji-flow fixtures.")
    parser.add_argument("--output", type=Path, required=True, help="Fixture output directory")
    args = parser.parse_args()
    generate_fixtures(args.output)
    return 0
