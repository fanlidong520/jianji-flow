from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


VIDEO_SIZE = "320x180"
FRAME_RATE = 12
CREATION_TIME = "1970-01-01T00:00:00Z"


SCENARIOS = {
    "scenario-a-product": {
        "text_name": "script.txt",
        "text": (
            "Hook: A small product can make one repetitive task easier.\n"
            "Pain: The manual workflow repeats the same steps.\n"
            "Feature: The product groups the steps into one clear flow.\n"
            "Evidence: This synthetic demo shows the product, detail, and result.\n"
            "CTA: Try the smallest useful workflow first.\n"
        ),
        "reference": ("reference-product", "0x6cc6ff", 440, 1.6),
        "assets": [
            ("product-overview", "0x2d8a6e", 520, 1.0),
            ("product-detail", "0xffb347", 660, 1.0),
        ],
    },
    "scenario-b-talking": {
        "text_name": "transcript.txt",
        "text": (
            "Topic: A practical way to review a talking-head video.\n"
            "Claim: Clear claims are easier to follow when each has one explanation.\n"
            "Explanation: Keep the topic, reason, evidence, and conclusion distinct.\n"
            "Evidence: This synthetic sequence supplies short labeled talking clips.\n"
            "Conclusion: A simple structure makes review easier.\n"
        ),
        "reference": ("reference-talking", "0xff8a65", 330, 1.6),
        "assets": [
            ("talking-wide", "0x7654d6", 390, 1.0),
            ("talking-detail", "0x42a5f5", 730, 1.0),
        ],
    },
}


def _make_video(output: Path, label: str, color: str, frequency: int, duration: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to generate synthetic fixtures")

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={VIDEO_SIZE}:r={FRAME_RATE}:d={duration}",
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
        str(output),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or "no diagnostic output"
        raise RuntimeError(f"ffmpeg failed for {output}: {detail}")


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


if __name__ == "__main__":
    raise SystemExit(main())
