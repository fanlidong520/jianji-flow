from __future__ import annotations

import shutil
import os
import math
import struct
import wave
from pathlib import Path

from jianji_flow.cli import main as cli_main
from jianji_flow.media_probe import run_ffprobe

from generate_fixtures import generate_fixtures


ROOT = Path(__file__).resolve().parents[1]


def _assert_outputs(work_dir: Path) -> None:
    for name in (
        "manifest.json",
        "recipe.json",
        "matches.json",
        "captions.srt",
        "captions.ass",
        "voiceover.wav",
        "remix.mp4",
        "contact-sheet.png",
        "review.md",
        "review.html",
    ):
        path = work_dir / name
        if not path.exists():
            raise AssertionError(f"missing smoke output: {path}")
    info = run_ffprobe(work_dir / "remix.mp4")
    if info.duration_ms <= 0:
        raise AssertionError(f"invalid smoke remix duration: {work_dir / 'remix.mp4'}")
    if not info.has_audio:
        raise AssertionError(f"smoke remix has no audio: {work_dir / 'remix.mp4'}")


def _write_test_wav(path: Path, *, seconds: float = 5.0) -> None:
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
        handle.writeframes(frames)


def _run_case(
    mode: str,
    scenario: str,
    script_name: str,
    fixture_root: Path,
    run_root: Path,
    voiceover: Path,
) -> None:
    work_dir = run_root / scenario
    code = cli_main(
        [
            "run",
            "--mode",
            mode,
            "--reference",
            str(fixture_root / scenario / "reference.mp4"),
            "--assets",
            str(fixture_root / scenario / "assets"),
            "--script",
            str(fixture_root / scenario / script_name),
            "--work-dir",
            str(work_dir),
            "--voiceover",
            str(voiceover),
            "--target-width",
            "320",
            "--target-height",
            "180",
            "--target-fps",
            "12",
        ]
    )
    if code != 0:
        raise AssertionError(f"smoke case failed: {scenario}")
    _assert_outputs(work_dir)


def main() -> int:
    smoke_root = ROOT / "out" / f"smoke-{os.getpid()}"
    if smoke_root.exists():
        shutil.rmtree(smoke_root)
    smoke_root.mkdir(parents=True, exist_ok=True)
    fixture_root = smoke_root / "fixtures"
    generate_fixtures(fixture_root)
    voiceover = smoke_root / "test-voiceover.wav"
    _write_test_wav(voiceover)

    _run_case("product", "scenario-a-product", "script.txt", fixture_root, smoke_root, voiceover)
    _run_case("talking-head", "scenario-b-talking", "transcript.txt", fixture_root, smoke_root, voiceover)
    print("smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
