from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageOps

from jianji_flow.contracts import validate_matches, validate_visual_selection
from jianji_flow.window_scoring import score_frame_information


MAX_CANDIDATES_PER_SEGMENT = 12
FRAME_FRACTIONS = (0.25, 0.5, 0.75)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _asset_path(asset: Any) -> str:
    value = _field(asset, "path", "")
    return Path(str(value)).as_posix()


def _asset_id(asset: Any) -> str:
    return str(_field(asset, "asset_id", _field(asset, "id", "")))


def _asset_sha256(asset: Any) -> str:
    value = _field(asset, "sha256", "")
    if value:
        return str(value)
    path = Path(_asset_path(asset))
    if not path.exists():
        return ""
    return _sha256(path)


def _duration_ms(asset: Any) -> int:
    return int(_field(asset, "duration_ms", 0))


def _segment_duration_ms(segment: dict) -> int:
    return int(segment["end_ms"]) - int(segment["start_ms"])


def _candidate_starts(asset_duration_ms: int, segment_duration_ms: int) -> list[int]:
    available = max(0, asset_duration_ms - segment_duration_ms)
    return list(dict.fromkeys((0, round(available * 0.5), available)))


def _candidate_id(segment_id: str, index: int) -> str:
    return f"{segment_id}-candidate-{index:02d}"


def build_visual_candidate_manifest(
    segments: list[dict],
    assets: Iterable[Any],
    work_dir: Path,
    *,
    max_candidates_per_segment: int = MAX_CANDIDATES_PER_SEGMENT,
) -> dict:
    ordered_assets = sorted(list(assets), key=lambda item: (_asset_id(item), _asset_path(item)))
    candidates: list[dict] = []
    for segment in segments:
        segment_id = str(segment.get("id", ""))
        segment_duration_ms = _segment_duration_ms(segment)
        if not segment_id or segment_duration_ms <= 0:
            continue
        segment_candidates: list[dict] = []
        for asset in ordered_assets:
            asset_duration_ms = _duration_ms(asset)
            if asset_duration_ms < segment_duration_ms:
                continue
            for source_start_ms in _candidate_starts(asset_duration_ms, segment_duration_ms):
                segment_candidates.append(
                    {
                        "candidate_id": _candidate_id(segment_id, len(segment_candidates) + 1),
                        "segment_id": segment_id,
                        "asset_id": _asset_id(asset),
                        "asset_path": _asset_path(asset),
                        "asset_sha256": _asset_sha256(asset),
                        "asset_duration_ms": asset_duration_ms,
                        "segment_duration_ms": segment_duration_ms,
                        "source_start_ms": source_start_ms,
                        "source_end_ms": source_start_ms + segment_duration_ms,
                        "available": True,
                        "frames": [],
                        "quality": {"frame_information": None, "is_semantic": False},
                        "reasons": ["candidate generated from visual window sampling"],
                        "warnings": [],
                    }
                )

        if len(segment_candidates) > max_candidates_per_segment:
            segment_candidates = _sample_candidates(segment_candidates, max_candidates_per_segment)
            for index, candidate in enumerate(segment_candidates, start=1):
                candidate["candidate_id"] = _candidate_id(segment_id, index)
        candidates.extend(segment_candidates)

    return {
        "version": "0.1",
        "generated_in": Path(work_dir).as_posix(),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def _sample_candidates(candidates: list[dict], limit: int) -> list[dict]:
    if limit <= 0:
        return []
    if len(candidates) <= limit:
        return candidates
    indexes = [round(index * (len(candidates) - 1) / (limit - 1)) for index in range(limit)]
    return [candidates[index] for index in indexes]


def write_visual_candidate_artifacts(manifest: dict, segments: list[dict], work_dir: Path) -> dict[str, str]:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = work_dir / "visual-candidates"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    for candidate in manifest.get("candidates", []):
        _write_candidate_frames(candidate, work_dir)

    manifest_path = work_dir / "visual-candidates.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sheet_path = work_dir / "visual-candidate-sheet.png"
    _write_candidate_sheet(manifest, segments, sheet_path)
    template_path = work_dir / "visual-selection.template.json"
    template = {
        "version": "0.1",
        "candidate_manifest": manifest_path.name,
        "selections": {
            str(segment["id"]): {
                "role": str(segment.get("role", "")),
                "caption": str(segment.get("caption", "")),
                "candidate_id": "",
                "reviewer": "codex-vision",
                "reason": "",
            }
            for segment in segments
        },
    }
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "visual_candidate_manifest": manifest_path.as_posix(),
        "visual_candidate_sheet": sheet_path.as_posix(),
        "visual_selection_template": template_path.as_posix(),
        "visual_candidate_frames": frames_dir.as_posix(),
    }


def _write_candidate_frames(candidate: dict, work_dir: Path) -> None:
    candidate["frames"] = []
    candidate["warnings"] = []
    candidate["available"] = True
    quality_samples: list[float] = []
    duration_ms = int(candidate["source_end_ms"]) - int(candidate["source_start_ms"])
    for index, fraction in enumerate(FRAME_FRACTIONS, start=1):
        time_ms = int(candidate["source_start_ms"] + round(duration_ms * fraction))
        relative_path = Path("visual-candidates") / f"{candidate['candidate_id']}-{index:02d}.png"
        frame_path = work_dir / relative_path
        try:
            _extract_frame(Path(str(candidate["asset_path"])), frame_path, time_ms)
            with Image.open(frame_path) as image:
                quality = score_frame_information(image.convert("RGB"))
            frame_sha = _sha256(frame_path)
        except (OSError, RuntimeError, ValueError) as exc:
            candidate["available"] = False
            candidate["warnings"].append(f"frame extraction failed at {time_ms}ms: {exc}")
            continue
        candidate["frames"].append(
            {
                "path": relative_path.as_posix(),
                "time_ms": time_ms,
                "sha256": frame_sha,
            }
        )
        quality_samples.append(quality)
        candidate["quality"]["frame_information"] = round(sum(quality_samples) / len(quality_samples), 6)
    if len(candidate["frames"]) != len(FRAME_FRACTIONS):
        candidate["available"] = False
    candidate["quality"]["is_semantic"] = False


def _write_candidate_sheet(manifest: dict, segments: list[dict], output_path: Path) -> None:
    by_segment: dict[str, list[dict]] = {}
    for candidate in manifest.get("candidates", []):
        by_segment.setdefault(str(candidate.get("segment_id", "")), []).append(candidate)
    columns = 4
    tile_width, tile_height = 180, 270
    title_height = 28
    segment_rows: list[tuple[str, list[dict]]] = []
    for segment in segments:
        items = by_segment.get(str(segment.get("id", "")), [])
        for offset in range(0, len(items), columns):
            segment_rows.append((str(segment.get("id", "")), items[offset : offset + columns]))
    if not segment_rows:
        segment_rows = [("no-candidates", [])]
    sheet = Image.new("RGB", (columns * tile_width, len(segment_rows) * tile_height), "#202124")
    draw = ImageDraw.Draw(sheet)
    for row_index, (segment_id, items) in enumerate(segment_rows):
        top = row_index * tile_height
        draw.text((8, top + 6), segment_id, fill="white")
        for column, candidate in enumerate(items):
            left = column * tile_width
            frame = _representative_frame(candidate, output_path.parent)
            if frame is not None:
                with Image.open(frame) as image:
                    fitted = ImageOps.fit(image.convert("RGB"), (tile_width - 8, tile_height - title_height - 8))
                    sheet.paste(fitted, (left + 4, top + title_height))
            label = str(candidate.get("candidate_id", ""))
            draw.rectangle((left + 4, top + 4, left + tile_width - 4, top + title_height - 2), fill="#111111")
            draw.text((left + 8, top + 8), label, fill="white")
    sheet.save(output_path)


def _representative_frame(candidate: dict, work_dir: Path) -> Path | None:
    frames = candidate.get("frames", [])
    if not frames:
        return None
    frame = frames[len(frames) // 2]
    path = work_dir / str(frame.get("path", ""))
    return path if path.exists() else None


def load_visual_selection(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"visual selection file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"visual selection file must contain a JSON object: {path}")
    try:
        validate_visual_selection(data)
    except Exception as exc:
        raise ValueError(f"visual selection schema error: {exc}") from exc
    return data


def apply_visual_selections(
    segments: list[dict],
    matches: dict,
    assets: list[Any],
    selection: dict,
    candidate_manifest: dict,
) -> dict:
    candidate_by_id = {str(item.get("candidate_id")): item for item in candidate_manifest.get("candidates", [])}
    segment_by_id = {str(segment.get("id")): segment for segment in segments}
    asset_by_id = {_asset_id(asset): asset for asset in assets}
    match_by_segment = {str(match.get("segment_id")): match for match in matches.get("matches", [])}
    updates: dict[str, dict] = {}

    for segment_id, selection_entry in selection.get("selections", {}).items():
        segment_id = str(segment_id)
        if segment_id not in segment_by_id:
            raise ValueError(f"visual selection segment not found: {segment_id}")
        candidate_id = str(selection_entry.get("candidate_id", ""))
        candidate = candidate_by_id.get(candidate_id)
        if candidate is None:
            raise ValueError(f"visual selection candidate not found: {candidate_id}")
        if str(candidate.get("segment_id")) != segment_id:
            raise ValueError(
                f"visual selection candidate {candidate_id} belongs to segment {candidate.get('segment_id')}, not {segment_id}"
            )
        if not candidate.get("available", False):
            raise ValueError(f"visual selection candidate is unavailable: {candidate_id}")
        asset = asset_by_id.get(str(candidate.get("asset_id")))
        if asset is None:
            raise ValueError(f"visual selection asset not found: {candidate.get('asset_id')}")
        if _asset_path(asset).casefold() != Path(str(candidate.get("asset_path", ""))).as_posix().casefold():
            raise ValueError(f"visual selection asset path changed; create a fresh candidate board for {candidate_id}")
        if _asset_sha256(asset) != str(candidate.get("asset_sha256", "")):
            raise ValueError(f"visual selection asset fingerprint changed for {candidate_id}")

        segment_duration_ms = _segment_duration_ms(segment_by_id[segment_id])
        start_ms = int(candidate.get("source_start_ms", -1))
        end_ms = int(candidate.get("source_end_ms", -1))
        if end_ms - start_ms != segment_duration_ms:
            raise ValueError(f"visual selection candidate duration does not match segment: {candidate_id}")
        if start_ms < 0 or end_ms > _duration_ms(asset):
            raise ValueError(f"visual selection source range is outside asset duration: {candidate_id}")
        if len(candidate.get("frames", [])) != len(FRAME_FRACTIONS):
            raise ValueError(f"visual selection candidate has no complete frame evidence: {candidate_id}")
        manifest_root = str(candidate_manifest.get("generated_in", "")).strip()
        if manifest_root:
            for frame in candidate.get("frames", []):
                frame_path = Path(manifest_root) / str(frame.get("path", ""))
                if not frame_path.exists():
                    raise ValueError(f"visual selection frame evidence is missing: {candidate_id}")
                if _sha256(frame_path) != str(frame.get("sha256", "")):
                    raise ValueError(f"visual selection frame fingerprint changed for {candidate_id}")

        existing = match_by_segment.get(segment_id)
        if existing is None:
            raise ValueError(f"visual selection match not found for segment: {segment_id}")
        evidence = [item for item in existing.get("evidence", []) if not str(item).startswith("visual-review:")]
        evidence.append(f"visual-review:{candidate_id}")
        scores = dict(existing.get("scores", {}))
        scores["visual_review"] = 1.0
        selected_candidate = {
            "asset_id": _asset_id(asset),
            "source_path": _asset_path(asset),
            "source_start_ms": start_ms,
            "source_end_ms": end_ms,
            "asset_duration_ms": _duration_ms(asset),
            "score": 1.0,
            "evidence": [f"visual-review:{candidate_id}"],
        }
        updates[segment_id] = {
            **existing,
            "status": "selected",
            "asset_id": _asset_id(asset),
            "source_path": _asset_path(asset),
            "source_start_ms": start_ms,
            "source_end_ms": end_ms,
            "asset_duration_ms": _duration_ms(asset),
            "confidence": 1.0,
            "scores": scores,
            "candidates": [selected_candidate],
            "evidence": evidence,
        }

    updated_matches = {
        **matches,
        "matches": [updates.get(str(match.get("segment_id")), dict(match)) for match in matches.get("matches", [])],
    }
    validate_matches(updated_matches)
    return updated_matches


def _extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
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
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"frame extraction failed at {time_ms}ms")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
