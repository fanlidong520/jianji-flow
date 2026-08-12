from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageStat

from jianji_flow.media_probe import run_ffprobe


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = PROJECT_ROOT / "scripts" / "generate_fixtures.py"


def _run_generator(output: Path) -> None:
    subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(output)],
        cwd=PROJECT_ROOT,
        check=True,
    )


def test_generator_creates_both_synthetic_scenarios(tmp_path: Path):
    output = tmp_path / "fixtures"

    _run_generator(output)

    assert (output / "scenario-a-product" / "script.txt").read_text(encoding="utf-8")
    assert (output / "scenario-b-talking" / "transcript.txt").read_text(encoding="utf-8")
    for scenario in ("scenario-a-product", "scenario-b-talking"):
        scenario_dir = output / scenario
        assert (scenario_dir / "reference.mp4").is_file()
        assert (scenario_dir / "assets").is_dir()
        assert list((scenario_dir / "assets").glob("*.mp4"))


def test_product_fixture_assets_use_quick_role_names(tmp_path: Path):
    output = tmp_path / "fixtures"
    _run_generator(output)

    names = {path.name for path in (output / "scenario-a-product" / "assets").glob("*.mp4")}

    assert names == {
        "01-hook-opening.mp4",
        "02-pain-before.mp4",
        "03-feature-product-detail.mp4",
        "04-evidence-demo-after.mp4",
        "05-cta-packshot-buy.mp4",
    }


@pytest.mark.parametrize("scenario", ["scenario-a-product", "scenario-b-talking"])
def test_generated_media_is_probeable_and_has_audio(tmp_path: Path, scenario: str):
    output = tmp_path / "fixtures"
    _run_generator(output)
    scenario_dir = output / scenario

    media_files = [scenario_dir / "reference.mp4", *sorted((scenario_dir / "assets").glob("*.mp4"))]
    for media_path in media_files:
        info = run_ffprobe(media_path)
        assert 0 < info.duration_ms <= 9000
        assert (info.width, info.height) == (320, 180)
        assert 0 < info.fps <= 30
        assert info.has_audio is True


def test_generated_fixture_frames_are_not_plain_color_blocks(tmp_path: Path):
    output = tmp_path / "fixtures"
    frame_path = tmp_path / "frame.png"
    _run_generator(output)
    media_path = output / "scenario-a-product" / "assets" / "01-hook-opening.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "0.2",
            "-i",
            str(media_path),
            "-frames:v",
            "1",
            str(frame_path),
        ],
        check=True,
    )

    image = Image.open(frame_path).convert("RGB")
    extrema = image.getextrema()
    stat = ImageStat.Stat(image)
    assert any(high - low > 40 for low, high in extrema)
    assert max(stat.stddev) > 20


def test_generator_output_is_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _run_generator(first)
    _run_generator(second)

    first_files = sorted(path.relative_to(first) for path in first.rglob("*" ) if path.is_file())
    second_files = sorted(path.relative_to(second) for path in second.rglob("*" ) if path.is_file())
    assert first_files == second_files
    for relative_path in first_files:
        first_hash = hashlib.sha256((first / relative_path).read_bytes()).digest()
        second_hash = hashlib.sha256((second / relative_path).read_bytes()).digest()
        assert first_hash == second_hash, relative_path


def test_generator_includes_a_damaged_media_fixture(tmp_path: Path):
    output = tmp_path / "fixtures"
    _run_generator(output)
    damaged = output / "malformed" / "damaged.mp4"

    assert damaged.is_file()
    with pytest.raises(RuntimeError):
        run_ffprobe(damaged)
