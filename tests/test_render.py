import shutil
import subprocess
import sys
import math
import struct
import wave
from pathlib import Path

import pytest
from PIL import Image, ImageStat

from jianji_flow.media_probe import run_ffprobe
from jianji_flow.render import build_ffmpeg_plan, render_preview


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = PROJECT_ROOT / "scripts" / "generate_fixtures.py"


def _write_tone_wav(path: Path, *, seconds: float = 0.25) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    frames = bytearray()
    for index in range(int(sample_rate * seconds)):
        value = int(math.sin(index / sample_rate * 440 * math.tau) * 8000)
        frames.extend(struct.pack("<h", value))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))


def _recipe(source_path: Path | str) -> tuple[dict, dict]:
    recipe = {
        "version": "0.1",
        "mode": "product",
        "duration_ms": 1000,
        "target": {"width": 320, "height": 180, "fps": 12},
        "audio_strategy": "silent-preview",
        "segments": [
            {
                "id": "seg-001",
                "role": "hook",
                "start_ms": 0,
                "end_ms": 1000,
                "match_id": "match-001",
                "caption": "Hook",
            }
        ],
    }
    matches = {
        "version": "0.1",
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-001",
                "source_path": str(source_path),
                "source_start_ms": 0,
                "source_end_ms": 1000,
                "confidence": 0.9,
                "scores": {},
                "candidates": [],
                "evidence": [],
            }
        ],
    }
    return recipe, matches


def _manifest(source_path: Path | str, asset_root: Path | str = "assets", reference_path: Path | str = "reference.mp4") -> dict:
    return {
        "version": "0.1",
        "asset_root": str(asset_root),
        "reference": str(reference_path),
        "assets": [
            {
                "asset_id": "asset-001",
                "path": str(source_path),
                "sha256": "0" * 64,
                "media_type": "video",
                "duration_ms": 1000,
                "width": 320,
                "height": 180,
                "fps": 12,
                "has_audio": True,
            }
        ],
    }


def test_render_command_uses_validated_inputs_only():
    recipe, matches = _recipe(Path("assets/hook.mp4"))

    command = build_ffmpeg_plan(
        recipe,
        matches,
        _manifest("assets/hook.mp4"),
        Path("out/remix.mp4"),
        work_dir=Path("out"),
        reference_path=Path("reference.mp4"),
        asset_root=Path("assets"),
        captions_path=None,
    )

    assert Path(command[0]).name.lower() in {"ffmpeg", "ffmpeg.exe"}
    assert "reference" not in " ".join(command).lower()
    assert "assets/hook.mp4" in command
    assert "-filter_complex" in command
    assert "out\\remix.mp4" not in command


def test_render_command_rejects_missing_match():
    recipe, matches = _recipe(Path("assets/hook.mp4"))
    matches["matches"][0] = {
        "id": "match-001",
        "segment_id": "seg-001",
        "status": "missing",
        "confidence": 0,
        "scores": {},
        "candidates": [],
        "evidence": [],
        "missing_reason": "none",
    }

    with pytest.raises(ValueError, match="cannot be rendered"):
        build_ffmpeg_plan(
            recipe,
            matches,
            _manifest("assets/hook.mp4"),
            Path("out/remix.mp4"),
            work_dir=Path("out"),
            reference_path=Path("reference.mp4"),
            asset_root=Path("assets"),
            captions_path=None,
        )


def test_render_command_rejects_protocol_source_path():
    recipe, matches = _recipe("s3:clip.mp4")

    with pytest.raises(ValueError, match="URL or protocol"):
        build_ffmpeg_plan(
            recipe,
            matches,
            _manifest("s3:clip.mp4"),
            Path("out/remix.mp4"),
            work_dir=Path("out"),
            reference_path=Path("reference.mp4"),
            asset_root=Path("assets"),
            captions_path=None,
        )


def test_render_command_rejects_output_outside_work_dir():
    recipe, matches = _recipe(Path("assets/hook.mp4"))

    with pytest.raises(ValueError, match="work_dir"):
        build_ffmpeg_plan(
            recipe,
            matches,
            _manifest("assets/hook.mp4"),
            Path("../outside.mp4"),
            work_dir=Path("out"),
            reference_path=Path("reference.mp4"),
            asset_root=Path("assets"),
            captions_path=None,
        )


def test_render_command_rejects_mismatched_source_range_duration():
    recipe, matches = _recipe(Path("assets/hook.mp4"))
    matches["matches"][0]["source_end_ms"] = 100

    with pytest.raises(ValueError, match="source range duration"):
        build_ffmpeg_plan(
            recipe,
            matches,
            _manifest("assets/hook.mp4"),
            Path("out/remix.mp4"),
            work_dir=Path("out"),
            reference_path=Path("reference.mp4"),
            asset_root=Path("assets"),
            captions_path=None,
        )


def test_render_command_uses_nonzero_source_start_and_declared_range():
    recipe, matches = _recipe(Path("assets/hook.mp4"))
    matches["matches"][0]["source_start_ms"] = 250
    matches["matches"][0]["source_end_ms"] = 1250
    manifest = _manifest("assets/hook.mp4")
    manifest["assets"][0]["duration_ms"] = 2000

    command = build_ffmpeg_plan(
        recipe,
        matches,
        manifest,
        Path("out/remix.mp4"),
        work_dir=Path("out"),
        reference_path=Path("reference.mp4"),
        asset_root=Path("assets"),
        captions_path=None,
    )

    assert command[command.index("-ss") + 1] == "0.250"
    assert command[command.index("-t") + 1] == "1.000"


def test_render_command_uses_voiceover_audio_and_burned_captions(tmp_path: Path):
    recipe, matches = _recipe(Path("assets/hook.mp4"))
    voiceover = tmp_path / "voiceover.wav"
    _write_tone_wav(voiceover)
    recipe["audio_strategy"] = "voiceover-only"
    recipe["voiceover_path"] = str(voiceover)
    recipe["caption_burn_in"] = True

    command = build_ffmpeg_plan(
        recipe,
        matches,
        _manifest("assets/hook.mp4"),
        Path("out/remix.mp4"),
        work_dir=Path("out"),
        reference_path=Path("reference.mp4"),
        asset_root=Path("assets"),
        captions_path=Path("out/captions.ass"),
        voiceover_path=voiceover,
    )

    assert "anullsrc=channel_layout=mono:sample_rate=48000" not in command
    assert str(voiceover) in command
    assert any("subtitles=" in part for part in command)


def test_render_command_uses_default_remix_visual_treatment_for_vertical_preview():
    recipe, matches = _recipe(Path("assets/hook.mp4"))
    recipe["target"] = {"width": 592, "height": 1280, "fps": 30}
    recipe["caption_burn_in"] = True

    command = build_ffmpeg_plan(
        recipe,
        matches,
        _manifest("assets/hook.mp4"),
        Path("out/remix.mp4"),
        work_dir=Path("out"),
        reference_path=Path("reference.mp4"),
        asset_root=Path("assets"),
        captions_path=Path("out/captions.ass"),
    )

    filter_complex = command[command.index("-filter_complex") + 1]
    assert "crop=iw*0.76:ih*0.58" in filter_complex
    assert "force_original_aspect_ratio=increase" in filter_complex
    assert "crop=592:1280" in filter_complex
    assert "drawbox=x=0:y=0" in filter_complex
    assert "drawbox=x=0:y=1119" in filter_complex


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg required")
def test_render_preview_creates_probeable_mp4(tmp_path: Path):
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    source_path = fixture_root / "scenario-a-product" / "assets" / "01-hook-opening.mp4"
    recipe, matches = _recipe(source_path)
    recipe_path = tmp_path / "recipe.json"
    matches_path = tmp_path / "matches.json"
    output_path = tmp_path / "work" / "remix.mp4"
    recipe_path.write_text(__import__("json").dumps(recipe), encoding="utf-8")
    matches_path.write_text(__import__("json").dumps(matches), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        __import__("json").dumps(
            _manifest(source_path, fixture_root / "scenario-a-product" / "assets", fixture_root / "scenario-a-product" / "reference.mp4")
        ),
        encoding="utf-8",
    )

    render_preview(
        recipe_path,
        matches_path,
        manifest_path,
        output_path,
        work_dir=output_path.parent,
        reference_path=fixture_root / "scenario-a-product" / "reference.mp4",
        asset_root=fixture_root / "scenario-a-product" / "assets",
    )

    info = run_ffprobe(output_path)
    assert 900 <= info.duration_ms <= 1200
    assert (info.width, info.height) == (320, 180)
    assert info.has_audio is True

    frame_path = tmp_path / "render-frame.png"
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
            str(output_path),
            "-frames:v",
            "1",
            str(frame_path),
        ],
        check=True,
    )
    frame = Image.open(frame_path).convert("RGB")
    extrema = frame.getextrema()
    stat = ImageStat.Stat(frame)
    assert any(high - low > 40 for low, high in extrema)
    assert max(stat.stddev) > 20


def test_render_preview_removes_stale_output_on_validation_failure(tmp_path: Path):
    recipe, matches = _recipe("s3:clip.mp4")
    recipe_path = tmp_path / "recipe.json"
    matches_path = tmp_path / "matches.json"
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "work" / "remix.mp4"
    output_path.parent.mkdir()
    output_path.write_bytes(b"old remix")
    recipe_path.write_text(__import__("json").dumps(recipe), encoding="utf-8")
    matches_path.write_text(__import__("json").dumps(matches), encoding="utf-8")
    manifest_path.write_text(__import__("json").dumps(_manifest("s3:clip.mp4")), encoding="utf-8")

    with pytest.raises(ValueError):
        render_preview(
            recipe_path,
            matches_path,
            manifest_path,
            output_path,
            work_dir=output_path.parent,
            reference_path=Path("reference.mp4"),
            asset_root=Path("assets"),
        )

    assert not output_path.exists()


def test_render_preview_rejects_outside_output_before_mutating_files(tmp_path: Path):
    recipe, matches = _recipe("assets/hook.mp4")
    recipe_path = tmp_path / "recipe.json"
    matches_path = tmp_path / "matches.json"
    manifest_path = tmp_path / "manifest.json"
    outside_dir = tmp_path / "outside"
    output_path = outside_dir / "remix.mp4"
    recipe_path.write_text(__import__("json").dumps(recipe), encoding="utf-8")
    matches_path.write_text(__import__("json").dumps(matches), encoding="utf-8")
    manifest_path.write_text(__import__("json").dumps(_manifest("assets/hook.mp4")), encoding="utf-8")

    with pytest.raises(ValueError, match="work_dir"):
        render_preview(
            recipe_path,
            matches_path,
            manifest_path,
            output_path,
            work_dir=tmp_path / "work",
            reference_path=Path("reference.mp4"),
            asset_root=Path("assets"),
        )

    assert not outside_dir.exists()


def test_render_preview_rejects_protocol_output_before_mutating_files(tmp_path: Path):
    recipe, matches = _recipe("assets/hook.mp4")
    recipe_path = tmp_path / "recipe.json"
    matches_path = tmp_path / "matches.json"
    manifest_path = tmp_path / "manifest.json"
    recipe_path.write_text(__import__("json").dumps(recipe), encoding="utf-8")
    matches_path.write_text(__import__("json").dumps(matches), encoding="utf-8")
    manifest_path.write_text(__import__("json").dumps(_manifest("assets/hook.mp4")), encoding="utf-8")

    with pytest.raises(ValueError, match="URL or protocol"):
        render_preview(
            recipe_path,
            matches_path,
            manifest_path,
            Path("s3:remix.mp4"),
            work_dir=tmp_path / "work",
            reference_path=Path("reference.mp4"),
            asset_root=Path("assets"),
        )

    assert not (tmp_path / "work").exists()
