from __future__ import annotations

import shutil
import subprocess
from html import escape
from pathlib import Path
from typing import Any

from jianji_flow.media_probe import run_ffprobe


def write_candidate_review(
    recipe: dict,
    matches: dict,
    fixes: dict,
    output_path: Path,
    *,
    frames_dir: Path,
    max_candidates: int = 3,
) -> dict[str, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    rows = _candidate_rows(recipe, matches, fixes, output_path.parent, frames_dir, max_candidates=max_candidates)
    output_path.write_text(_build_candidate_review_html(rows), encoding="utf-8")
    return {
        "candidate_review": output_path.as_posix(),
        "candidate_frames": frames_dir.as_posix(),
    }


def _candidate_rows(
    recipe: dict,
    matches: dict,
    fixes: dict,
    base_dir: Path,
    frames_dir: Path,
    *,
    max_candidates: int,
) -> list[dict[str, Any]]:
    match_by_id = {str(match.get("id")): match for match in matches.get("matches", [])}
    fix_segments = fixes.get("segments", {})
    if not isinstance(fix_segments, dict):
        return []

    rows = []
    for segment in recipe.get("segments", []):
        segment_id = str(segment.get("id", ""))
        fix = fix_segments.get(segment_id)
        if not isinstance(fix, dict):
            continue
        match = match_by_id.get(str(segment.get("match_id")), {})
        safe_segment_id = _safe_name(segment_id or "segment")
        current_path = _first_text(fix.get("current_asset_path"), match.get("source_path"))
        current_start_ms = _int_value(match.get("source_start_ms"), _int_value(fix.get("source_start_ms"), 0))
        source_duration_ms = _source_duration_ms(match, segment)
        current_frame = _frame_entry(
            Path(current_path),
            frames_dir / f"{safe_segment_id}-current.png",
            current_start_ms + round(source_duration_ms / 2),
            base_dir,
        )
        rows.append(
            {
                "segment_id": segment_id,
                "role": _first_text(fix.get("role"), segment.get("role")),
                "caption": _first_text(fix.get("caption"), segment.get("caption")),
                "reason": str(fix.get("reason", "")),
                "status": str(fix.get("recommendation_status", "")),
                "recommendation_warnings": [str(item) for item in fix.get("recommendation_warnings", [])],
                "current": {
                    "asset_path": current_path,
                    "source_range": _source_range_text(match),
                    **current_frame,
                },
                "candidates": _candidate_entries(
                    fix,
                    frames_dir,
                    base_dir,
                    safe_segment_id=safe_segment_id,
                    current_start_ms=current_start_ms,
                    source_duration_ms=source_duration_ms,
                    max_candidates=max_candidates,
                ),
            }
        )
    return rows


def _candidate_entries(
    fix: dict,
    frames_dir: Path,
    base_dir: Path,
    *,
    safe_segment_id: str,
    current_start_ms: int,
    source_duration_ms: int,
    max_candidates: int,
) -> list[dict[str, Any]]:
    recommended_path = _path_key(str(fix.get("recommended_asset_path", "")))
    recommended_start_ms = _optional_int(fix.get("recommended_source_start_ms"))
    candidates = [candidate for candidate in fix.get("candidate_assets", []) if isinstance(candidate, dict)]
    selected = _top_candidates(
        candidates,
        recommended_path,
        recommended_start_ms,
        max_candidates=max_candidates,
    )
    entries = []
    for index, candidate in enumerate(selected, start=1):
        asset_path = str(candidate.get("asset_path", ""))
        candidate_start_ms = _optional_int(candidate.get("source_start_ms"))
        candidate_end_ms = _optional_int(candidate.get("source_end_ms"))
        sample_ms = (
            candidate_start_ms + round(source_duration_ms / 2)
            if candidate_start_ms is not None
            else _candidate_sample_ms(Path(asset_path), current_start_ms, source_duration_ms)
        )
        frame = _frame_entry(
            Path(asset_path),
            frames_dir / f"{safe_segment_id}-candidate-{index:03d}.png",
            sample_ms,
            base_dir,
        )
        entries.append(
            {
                "label": (
                    "Recommended candidate"
                    if _candidate_key(asset_path, candidate_start_ms) == _candidate_key_from_parts(recommended_path, recommended_start_ms)
                    else f"Candidate {index}"
                ),
                "asset_path": asset_path,
                "score": candidate.get("score", ""),
                "source_range": _candidate_source_range_text(candidate_start_ms, candidate_end_ms),
                "preview_frame_ms": sample_ms,
                "reasons": [str(item) for item in candidate.get("reasons", [])],
                "warnings": [str(item) for item in candidate.get("warnings", [])],
                "role_match": bool(candidate.get("role_match")),
                **frame,
            }
        )
    return entries


def _top_candidates(
    candidates: list[dict],
    recommended_path: str,
    recommended_start_ms: int | None,
    *,
    max_candidates: int,
) -> list[dict]:
    selected = candidates[: max(0, max_candidates)]
    recommended_key = _candidate_key_from_parts(recommended_path, recommended_start_ms)
    if recommended_path and not any(_candidate_key_for_candidate(candidate) == recommended_key for candidate in selected):
        recommended = next(
            (candidate for candidate in candidates if _candidate_key_for_candidate(candidate) == recommended_key),
            None,
        )
        if recommended is not None:
            selected = selected[: max(0, max_candidates - 1)] + [recommended]
    return selected


def _frame_entry(video_path: Path, frame_path: Path, sample_ms: int, base_dir: Path) -> dict[str, str]:
    try:
        _extract_frame(video_path, frame_path, max(0, sample_ms))
    except (OSError, RuntimeError, ValueError) as exc:
        return {"frame_src": "", "frame_error": str(exc)}
    return {"frame_src": _relative_src(frame_path, base_dir), "frame_error": ""}


def _extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-ss",
        f"{time_ms / 1000:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        str(frame_path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        detail = result.stderr.strip() or f"frame extraction failed at {time_ms}ms"
        raise RuntimeError(detail)
    if not frame_path.exists() or frame_path.stat().st_size <= 0:
        raise RuntimeError(f"frame extraction produced no image at {time_ms}ms")


def _candidate_sample_ms(video_path: Path, current_start_ms: int, source_duration_ms: int) -> int:
    start_ms = max(0, current_start_ms)
    try:
        info = run_ffprobe(video_path)
    except (OSError, RuntimeError, ValueError):
        return start_ms + round(source_duration_ms / 2)
    max_start_ms = max(0, int(info.duration_ms) - source_duration_ms)
    return min(start_ms, max_start_ms) + round(source_duration_ms / 2)


def _source_duration_ms(match: dict, segment: dict) -> int:
    source_start = _int_value(match.get("source_start_ms"), 0)
    source_end = _int_value(match.get("source_end_ms"), 0)
    if source_end > source_start:
        return source_end - source_start
    segment_start = _int_value(segment.get("start_ms"), 0)
    segment_end = _int_value(segment.get("end_ms"), 0)
    return max(1, segment_end - segment_start)


def _source_range_text(match: dict) -> str:
    source_start = match.get("source_start_ms")
    source_end = match.get("source_end_ms")
    if isinstance(source_start, int) and isinstance(source_end, int):
        return f"{source_start}-{source_end}ms"
    return "unknown"


def _build_candidate_review_html(rows: list[dict[str, Any]]) -> str:
    content = "".join(_segment_html(row) for row in rows) if rows else "<p>No fix candidates were generated for this run.</p>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>jianji-flow candidate review</title>
  <style>
    body {{ font-family: Arial, "Microsoft YaHei", sans-serif; margin: 24px; color: #151719; background: #f7f8fa; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    article {{ background: #fff; border: 1px solid #d6dae0; margin: 0 0 18px; padding: 16px; }}
    h1 {{ margin-top: 0; }}
    h2 {{ margin: 0 0 6px; }}
    h3 {{ margin: 0 0 8px; font-size: 16px; }}
    img {{ display: block; width: 100%; max-width: 360px; border: 1px solid #c9ced6; background: #000; }}
    code {{ background: #eef1f4; padding: 2px 4px; overflow-wrap: anywhere; }}
    dl {{ display: grid; grid-template-columns: 130px 1fr; gap: 6px 10px; margin: 10px 0 0; }}
    dt {{ color: #5b6470; font-weight: 700; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    .comparison {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; margin-top: 14px; }}
    .panel {{ border: 1px solid #d6dae0; padding: 12px; }}
    .warning {{ color: #92400e; }}
    .missing {{ border: 1px dashed #9aa3af; padding: 22px; background: #fafafa; color: #5b6470; }}
  </style>
</head>
<body>
<main>
  <h1>Candidate Review</h1>
  {content}
</main>
</body>
</html>
"""


def _segment_html(row: dict[str, Any]) -> str:
    warnings = _list_text(row.get("recommendation_warnings", [])) or "none"
    candidate_panels = "".join(_candidate_html(candidate) for candidate in row.get("candidates", []))
    if not candidate_panels:
        candidate_panels = '<div class="panel missing">No candidate assets available.</div>'
    return (
        "<article>"
        f"<h2>{escape(str(row['segment_id']))} - {escape(str(row.get('role', '')))}</h2>"
        f"<p>{escape(str(row.get('caption', '')))}</p>"
        "<dl>"
        f"<dt>Reason</dt><dd>{escape(str(row.get('reason', '') or 'unknown'))}</dd>"
        f"<dt>Status</dt><dd>{escape(str(row.get('status', '') or 'unknown'))}</dd>"
        f"<dt>Warnings</dt><dd>{escape(warnings)}</dd>"
        "</dl>"
        "<section class=\"comparison\">"
        f"{_current_html(row['current'])}"
        f"{candidate_panels}"
        "</section>"
        "</article>"
    )


def _current_html(current: dict[str, str]) -> str:
    return (
        '<div class="panel">'
        "<h3>Current segment</h3>"
        f"{_image_or_error(current)}"
        "<dl>"
        f"<dt>Asset</dt><dd><code>{escape(str(current.get('asset_path', '')))}</code></dd>"
        f"<dt>Source range</dt><dd>{escape(str(current.get('source_range', 'unknown')))}</dd>"
        "</dl>"
        "</div>"
    )


def _candidate_html(candidate: dict[str, Any]) -> str:
    reasons = _list_text(candidate.get("reasons", [])) or "none"
    warnings = _list_text(candidate.get("warnings", [])) or "none"
    return (
        '<div class="panel">'
        f"<h3>{escape(str(candidate.get('label', 'Candidate')))}</h3>"
        f"{_image_or_error(candidate)}"
        "<dl>"
        f"<dt>Asset</dt><dd><code>{escape(str(candidate.get('asset_path', '')))}</code></dd>"
        f"<dt>Candidate window</dt><dd>{escape(str(candidate.get('source_range', 'unknown')))}</dd>"
        f"<dt>Preview frame</dt><dd>{escape(str(candidate.get('preview_frame_ms', 'unknown')))}ms</dd>"
        f"<dt>Score</dt><dd>{escape(str(candidate.get('score', '')))}</dd>"
        f"<dt>Role match</dt><dd>{escape(str(candidate.get('role_match', '')))}</dd>"
        f"<dt>Reasons</dt><dd>{escape(reasons)}</dd>"
        f"<dt>Warnings</dt><dd class=\"warning\">{escape(warnings)}</dd>"
        "</dl>"
        "</div>"
    )


def _image_or_error(item: dict[str, Any]) -> str:
    frame_src = str(item.get("frame_src", ""))
    if frame_src:
        return f'<img alt="candidate review frame" src="{escape(frame_src)}">'
    return f'<div class="missing">Frame unavailable: {escape(str(item.get("frame_error", "unknown error")))}</div>'


def _list_text(values: list[Any]) -> str:
    return "; ".join(str(value) for value in values)


def _relative_src(path: Path, base_dir: Path) -> str:
    try:
        return path.resolve().relative_to(base_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _candidate_source_range_text(start_ms: int | None, end_ms: int | None) -> str:
    if start_ms is None or end_ms is None:
        return "unknown"
    return f"{start_ms}-{end_ms}ms"


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value).strip("-") or "segment"


def _path_key(path_text: str) -> str:
    return path_text.replace("\\", "/").casefold()


def _candidate_key_for_candidate(candidate: dict[str, Any]) -> str:
    return _candidate_key(str(candidate.get("asset_path", "")), _optional_int(candidate.get("source_start_ms")))


def _candidate_key(asset_path: str, source_start_ms: int | None) -> str:
    return _candidate_key_from_parts(_path_key(asset_path), source_start_ms)


def _candidate_key_from_parts(path_key: str, source_start_ms: int | None) -> str:
    return f"{path_key}#{source_start_ms}"
