from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("scenario", ["scenario-a-product", "scenario-b-talking"])
def test_generated_media_is_probeable_and_has_audio(tmp_path: Path, scenario: str):
    output = tmp_path / "fixtures"
    _run_generator(output)
    scenario_dir = output / scenario

    media_files = [scenario_dir / "reference.mp4", *sorted((scenario_dir / "assets").glob("*.mp4"))]
    for media_path in media_files:
        info = run_ffprobe(media_path)
        assert 0 < info.duration_ms <= 3000
        assert (info.width, info.height) == (320, 180)
        assert 0 < info.fps <= 30
        assert info.has_audio is True


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
