from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MediaInfo:
    source_path: str
    duration_ms: int
    width: int
    height: int
    fps: float
    has_audio: bool
    rotation: int


def _parse_frame_rate(value: Any) -> float:
    if not isinstance(value, str) or "/" not in value:
        return 0.0
    numerator, denominator = value.split("/", 1)
    try:
        numerator_value = float(numerator)
        denominator_value = float(denominator)
    except ValueError:
        return 0.0
    if denominator_value == 0:
        return 0.0
    return numerator_value / denominator_value


def _parse_rotation(stream: dict[str, Any]) -> int:
    tags = stream.get("tags")
    if isinstance(tags, dict) and "rotate" in tags:
        try:
            return int(tags["rotate"])
        except (TypeError, ValueError):
            pass

    for side_data in stream.get("side_data_list", []):
        if isinstance(side_data, dict) and "rotation" in side_data:
            try:
                return int(side_data["rotation"])
            except (TypeError, ValueError):
                pass
    return 0


def parse_ffprobe_json(payload: dict, source_path: str) -> MediaInfo:
    if not isinstance(payload, dict):
        raise ValueError("ffprobe payload must be a JSON object")

    streams = payload.get("streams", [])
    video_stream = next(
        (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
        None,
    )
    if video_stream is None:
        raise ValueError("ffprobe payload does not contain a video stream")

    format_data = payload.get("format", {})
    try:
        duration_ms = int(round(float(format_data.get("duration", 0)) * 1000))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("ffprobe payload contains invalid media values") from exc

    return MediaInfo(
        source_path=source_path,
        duration_ms=duration_ms,
        width=width,
        height=height,
        fps=_parse_frame_rate(video_stream.get("avg_frame_rate")),
        has_audio=any(
            isinstance(stream, dict) and stream.get("codec_type") == "audio"
            for stream in streams
        ),
        rotation=_parse_rotation(video_stream),
    )


def run_ffprobe(path: Path, timeout_s: int = 30) -> MediaInfo:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            check=False,
            shell=False,
            timeout=timeout_s,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffprobe timed out after {timeout_s} seconds") from exc
    except OSError as exc:
        raise RuntimeError(f"could not run ffprobe: {exc}") from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or "no diagnostic output"
        raise RuntimeError(f"ffprobe failed with exit code {result.returncode}: {detail}")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("ffprobe returned invalid JSON output") from exc
    return parse_ffprobe_json(payload, str(path))


def _tool_status(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        return "missing"
    try:
        result = subprocess.run(
            [executable, "-version"],
            check=False,
            shell=False,
            timeout=5,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        return executable
    first_line = (result.stdout or "").splitlines()
    version = first_line[0].strip() if first_line else ""
    return f"{executable} ({version})" if version else executable


def check_ffmpeg_available() -> dict[str, str]:
    return {"ffmpeg": _tool_status("ffmpeg"), "ffprobe": _tool_status("ffprobe")}
