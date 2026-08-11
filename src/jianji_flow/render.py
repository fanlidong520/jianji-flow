from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from jianji_flow.paths import ensure_inside, reject_url_or_protocol
from jianji_flow.semantics import validate_semantics
from jianji_flow.voiceover import validate_voiceover


def _posix(path: Path) -> str:
    return path.as_posix()


def _match_by_id(matches: dict) -> dict[str, dict]:
    return {match["id"]: match for match in matches.get("matches", [])}


def _selected_sources(recipe: dict, matches: dict) -> list[tuple[dict, dict]]:
    by_id = _match_by_id(matches)
    selected = []
    for segment in recipe.get("segments", []):
        match = by_id.get(segment.get("match_id"))
        if match is None:
            raise ValueError(f"segment {segment.get('id')!r}: match is missing")
        if match.get("status") not in {"selected", "low_confidence"}:
            raise ValueError(f"segment {segment.get('id')!r}: match cannot be rendered")
        source_path = match.get("source_path")
        if not isinstance(source_path, str):
            raise ValueError(f"match {match.get('id')!r}: source_path must be a string")
        reject_url_or_protocol(source_path)
        source_duration = int(match["source_end_ms"]) - int(match["source_start_ms"])
        segment_duration = int(segment["end_ms"]) - int(segment["start_ms"])
        if source_duration != segment_duration:
            raise ValueError(f"match {match.get('id')!r}: source range duration must match recipe segment duration")
        selected.append((segment, match))
    return selected


def _subtitle_filter_path(path: Path) -> str:
    normalized = path.resolve().as_posix()
    return normalized.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _filter_complex(recipe: dict, source_count: int, captions_path: Path | None = None) -> str:
    target = recipe["target"]
    width = int(target["width"])
    height = int(target["height"])
    fps = float(target["fps"])
    video_filters = []
    video_labels = []
    for index in range(source_count):
        label = f"v{index}"
        video_filters.append(
            f"[{index}:v:0]"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={fps},setsar=1,setpts=PTS-STARTPTS"
            f"[{label}]"
        )
        video_labels.append(f"[{label}]")
    concat_filter = f"{''.join(video_labels)}concat=n={source_count}:v=1:a=0"
    if captions_path is None:
        return ";".join(video_filters + [f"{concat_filter}[vout]"])
    subtitles = f"subtitles=filename='{_subtitle_filter_path(captions_path)}'"
    return ";".join(video_filters + [f"{concat_filter}[vcat]", f"[vcat]{subtitles}[vout]"])


def build_ffmpeg_plan(
    recipe: dict,
    matches: dict,
    manifest: dict,
    output_path: Path,
    *,
    work_dir: Path,
    reference_path: Path,
    asset_root: Path,
    captions_path: Path | None = None,
    voiceover_path: Path | None = None,
) -> list[str]:
    reject_url_or_protocol(str(output_path))
    if captions_path is not None:
        reject_url_or_protocol(str(captions_path))
    if voiceover_path is not None:
        reject_url_or_protocol(str(voiceover_path))
    try:
        output_path = ensure_inside(work_dir, output_path)
    except ValueError as exc:
        raise ValueError("output_path must stay inside work_dir") from exc
    semantic_errors = validate_semantics(
        recipe,
        matches,
        manifest,
        str(reference_path),
        str(asset_root),
        str(work_dir),
    )
    if semantic_errors:
        raise ValueError("; ".join(semantic_errors))
    selected = _selected_sources(recipe, matches)
    if not selected:
        raise ValueError("recipe has no renderable segments")

    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    total_duration_s = 0.0
    for segment, match in selected:
        source_start_s = int(match["source_start_ms"]) / 1000
        duration_s = (int(match["source_end_ms"]) - int(match["source_start_ms"])) / 1000
        total_duration_s += duration_s
        command.extend(
            [
                "-ss",
                f"{source_start_s:.3f}",
                "-t",
                f"{duration_s:.3f}",
                "-i",
                str(match["source_path"]).replace("\\", "/"),
            ]
        )

    audio_strategy = recipe.get("audio_strategy", "silent-preview")
    if audio_strategy == "voiceover-only":
        resolved_voiceover = voiceover_path or Path(str(recipe.get("voiceover_path", "")))
        if not str(resolved_voiceover):
            raise ValueError("voiceover-only requires voiceover_path")
        validate_voiceover(resolved_voiceover)
        audio_input_index = len(selected)
        command.extend(["-i", str(resolved_voiceover)])
        audio_options = [
            "-map",
            "[vout]",
            "-map",
            f"{audio_input_index}:a:0",
            "-af",
            f"apad=whole_dur={total_duration_s:.3f}",
            "-t",
            f"{total_duration_s:.3f}",
        ]
    elif audio_strategy == "silent-preview":
        audio_input_index = len(selected)
        command.extend(
            [
                "-f",
                "lavfi",
                "-t",
                f"{total_duration_s:.3f}",
                "-i",
                "anullsrc=channel_layout=mono:sample_rate=48000",
            ]
        )
        audio_options = [
            "-map",
            "[vout]",
            "-map",
            f"{audio_input_index}:a:0",
            "-shortest",
        ]
    else:
        raise ValueError(f"unsupported audio_strategy: {audio_strategy}")

    command.extend(
        [
            "-filter_complex",
            _filter_complex(recipe, len(selected), captions_path),
            *audio_options,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            _posix(output_path),
        ]
    )
    return command


def render_preview(
    recipe_path: Path,
    matches_path: Path,
    manifest_path: Path,
    output_path: Path,
    *,
    work_dir: Path,
    reference_path: Path,
    asset_root: Path,
    captions_path: Path | None = None,
    voiceover_path: Path | None = None,
    timeout_s: int = 120,
) -> None:
    reject_url_or_protocol(str(output_path))
    try:
        output_path = ensure_inside(work_dir, output_path)
    except ValueError as exc:
        raise ValueError("output_path must stay inside work_dir") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    temp_path = output_path.with_name(f".{output_path.stem}.tmp{output_path.suffix}")
    if temp_path.exists():
        temp_path.unlink()

    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    matches = json.loads(matches_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    command = build_ffmpeg_plan(
        recipe,
        matches,
        manifest,
        temp_path,
        work_dir=work_dir,
        reference_path=reference_path,
        asset_root=asset_root,
        captions_path=captions_path,
        voiceover_path=voiceover_path,
    )
    try:
        result = subprocess.run(
            command,
            check=False,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or "no diagnostic output"
            raise RuntimeError(f"ffmpeg render failed: {detail}")
        temp_path.replace(output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
