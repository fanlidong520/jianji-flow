from __future__ import annotations

import hashlib
from pathlib import Path

from jianji_flow.paths import reject_url_or_protocol


def _is_inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _resolved(path_text: str) -> Path:
    return Path(path_text).resolve()


def _sha256_or_none(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return False


def _has_url_or_protocol(path_text: str) -> bool:
    try:
        reject_url_or_protocol(path_text)
    except ValueError:
        return True
    return False


def validate_semantics(
    recipe: dict,
    matches: dict,
    manifest: dict,
    reference_path: str,
    asset_root: str,
    work_dir: str,
) -> list[str]:
    errors: list[str] = []
    segments = recipe.get("segments", [])
    match_by_id = {item.get("id"): item for item in matches.get("matches", [])}
    manifest_by_id = {item.get("asset_id"): item for item in manifest.get("assets", [])}

    if _has_url_or_protocol(reference_path):
        errors.append("reference_path must not be a URL or protocol path")
    if _has_url_or_protocol(asset_root):
        errors.append("asset_root must not be a URL or protocol path")
    if _has_url_or_protocol(work_dir):
        errors.append("work_dir must not be a URL or protocol path")
    if errors:
        return errors

    resolved_asset_root = _resolved(asset_root)
    resolved_reference = _resolved(reference_path)
    resolved_work_dir = _resolved(work_dir)
    reference_hash = _sha256_or_none(resolved_reference)

    manifest_asset_root = manifest.get("asset_root")
    if manifest_asset_root and _resolved(manifest_asset_root) != resolved_asset_root:
        errors.append("manifest asset_root does not match provided asset_root")

    manifest_reference = manifest.get("reference")
    if manifest_reference and _resolved(manifest_reference) != resolved_reference:
        errors.append("manifest reference does not match provided reference_path")

    output_path = recipe.get("output_path")
    if output_path:
        if not isinstance(output_path, str) or _has_url_or_protocol(output_path):
            errors.append("recipe output_path must not be a URL or protocol path")
        elif not _is_inside(resolved_work_dir, _resolved(output_path)):
            errors.append("recipe output_path must stay inside work_dir")

    for asset in manifest.get("assets", []):
        asset_path = asset.get("path")
        if not isinstance(asset_path, str) or _has_url_or_protocol(asset_path):
            errors.append(f"manifest asset {asset.get('asset_id')!r}: path must not be a URL or protocol path")
            continue
        resolved_asset = _resolved(asset_path)
        if not _is_inside(resolved_asset_root, resolved_asset):
            errors.append(f"manifest asset {asset.get('asset_id')!r}: path is outside asset_root")
        if resolved_asset == resolved_reference or _same_file(resolved_asset, resolved_reference):
            errors.append(f"manifest asset {asset.get('asset_id')!r}: path resolves to reference_path")
        asset_hash = _sha256_or_none(resolved_asset)
        if reference_hash is not None and asset_hash == reference_hash:
            errors.append(f"manifest asset {asset.get('asset_id')!r}: file hash matches reference_path")

    for match in matches.get("matches", []):
        if match.get("status") not in {"selected", "low_confidence"}:
            continue
        source_path = match.get("source_path")
        if not isinstance(source_path, str) or _has_url_or_protocol(source_path):
            errors.append(f"match {match.get('id')!r}: source_path must not be a URL or protocol path")

    previous_end = None
    for index, segment in enumerate(segments):
        segment_id = segment.get("id", f"segment-{index + 1}")
        start = segment.get("start_ms")
        end = segment.get("end_ms")

        if start is None or end is None:
            errors.append(f"segment {segment_id}: missing timeline bounds")
        else:
            if index == 0 and start != 0:
                errors.append(f"segment {segment_id}: timeline must start at 0")
            if end <= start:
                errors.append(f"segment {segment_id}: end_ms must be greater than start_ms")
            if previous_end is not None:
                if start > previous_end:
                    errors.append(f"segment {segment_id}: timeline gap before segment")
                elif start < previous_end:
                    errors.append(f"segment {segment_id}: timeline overlaps previous segment")
            previous_end = end

        match_id = segment.get("match_id")
        if not match_id:
            errors.append(f"segment {segment_id}: match_id is missing")
            continue

        match = match_by_id.get(match_id)
        if match is None:
            errors.append(f"segment {segment_id}: match_id {match_id!r} is missing from matches")
            continue

        if match.get("segment_id") != segment.get("id"):
            errors.append(f"segment {segment_id}: match {match_id!r} segment_id does not match recipe segment")

        status = match.get("status")
        if status not in {"selected", "low_confidence"}:
            errors.append(f"segment {segment_id}: match {match_id!r} cannot be rendered")
            continue

        asset_id = match.get("asset_id")
        asset = manifest_by_id.get(asset_id)
        if asset is None:
            errors.append(f"match {match_id!r}: asset_id {asset_id!r} is missing from manifest")
        else:
            source_start = match.get("source_start_ms")
            source_end = match.get("source_end_ms")
            duration = asset.get("duration_ms")
            if (
                source_start is None
                or source_end is None
                or source_start < 0
                or source_end <= source_start
                or source_end > duration
            ):
                errors.append(f"match {match_id!r}: source range exceeds asset duration or is invalid")
            elif start is not None and end is not None:
                playback_rate = match.get("playback_rate")
                if playback_rate is None:
                    duration_matches = (source_end - source_start) == (end - start)
                else:
                    try:
                        duration_matches = round((source_end - source_start) / float(playback_rate)) == (end - start)
                    except (TypeError, ValueError, ZeroDivisionError):
                        duration_matches = False
                if not duration_matches:
                    errors.append(
                        f"match {match_id!r}: source range duration must match recipe segment duration"
                    )

        source_path = match.get("source_path")
        if not isinstance(source_path, str) or _has_url_or_protocol(source_path):
            errors.append(f"match {match_id!r}: source_path must not be a URL or protocol path")
            continue

        resolved_source = _resolved(source_path)
        if not _is_inside(resolved_asset_root, resolved_source):
            errors.append(f"match {match_id!r}: source_path is outside asset_root")
        if resolved_source == resolved_reference or _same_file(resolved_source, resolved_reference):
            errors.append(f"match {match_id!r}: source_path resolves to reference_path")
        source_hash = _sha256_or_none(resolved_source)
        if reference_hash is not None and source_hash == reference_hash:
            errors.append(f"match {match_id!r}: source_path file hash matches reference_path")
        if asset is not None:
            manifest_asset_path = asset.get("path")
            if (
                isinstance(manifest_asset_path, str)
                and not _has_url_or_protocol(manifest_asset_path)
                and resolved_source != _resolved(manifest_asset_path)
            ):
                errors.append(f"match {match_id!r}: source_path does not match manifest asset path")

        errors.extend(
            _validate_match_shots(
                match,
                segment,
                manifest_by_id,
                resolved_asset_root,
                resolved_reference,
                reference_hash,
            )
        )

    if segments and previous_end != recipe.get("duration_ms"):
        errors.append(
            f"timeline final end_ms {previous_end!r} does not equal recipe duration_ms {recipe.get('duration_ms')!r}"
        )

    return errors


def _validate_match_shots(
    match: dict,
    segment: dict,
    manifest_by_id: dict,
    asset_root: Path,
    reference_path: Path,
    reference_hash: str | None,
) -> list[str]:
    shots = match.get("shots")
    if not shots:
        return []

    errors: list[str] = []
    match_id = str(match.get("id", "unknown"))
    source_duration = int(match.get("source_end_ms", 0)) - int(match.get("source_start_ms", 0))
    playback_rate = match.get("playback_rate")
    if playback_rate is None:
        expected_duration = int(segment.get("end_ms", 0)) - int(segment.get("start_ms", 0))
    else:
        try:
            expected_duration = source_duration
            if round(source_duration / float(playback_rate)) != (
                int(segment.get("end_ms", 0)) - int(segment.get("start_ms", 0))
            ):
                errors.append(f"match {match_id!r}: playback_rate does not fit segment duration")
        except (TypeError, ValueError, ZeroDivisionError):
            errors.append(f"match {match_id!r}: playback_rate is invalid")
            expected_duration = source_duration
    total_duration = 0
    for index, shot in enumerate(shots, start=1):
        label = f"match {match_id!r} shot {index}"
        asset_id = shot.get("asset_id")
        asset = manifest_by_id.get(asset_id)
        if asset is None:
            errors.append(f"{label}: asset_id {asset_id!r} is missing from manifest")
            continue

        source_path = shot.get("source_path")
        if not isinstance(source_path, str) or _has_url_or_protocol(source_path):
            errors.append(f"{label}: source_path must not be a URL or protocol path")
            continue
        resolved_source = _resolved(source_path)
        if not _is_inside(asset_root, resolved_source):
            errors.append(f"{label}: source_path is outside asset_root")
        if resolved_source == reference_path or _same_file(resolved_source, reference_path):
            errors.append(f"{label}: source_path resolves to reference_path")
        source_hash = _sha256_or_none(resolved_source)
        if reference_hash is not None and source_hash == reference_hash:
            errors.append(f"{label}: source_path file hash matches reference_path")
        manifest_asset_path = asset.get("path")
        if (
            isinstance(manifest_asset_path, str)
            and not _has_url_or_protocol(manifest_asset_path)
            and resolved_source != _resolved(manifest_asset_path)
        ):
            errors.append(f"{label}: source_path does not match manifest asset path")

        start_ms = shot.get("source_start_ms")
        end_ms = shot.get("source_end_ms")
        duration_ms = asset.get("duration_ms")
        if (
            start_ms is None
            or end_ms is None
            or start_ms < 0
            or end_ms <= start_ms
            or end_ms > duration_ms
        ):
            errors.append(f"{label}: source range exceeds asset duration or is invalid")
            continue
        total_duration += end_ms - start_ms

    if total_duration != expected_duration:
        errors.append(
            f"match {match_id!r}: shot durations {total_duration}ms do not match segment duration {expected_duration}ms"
        )
    return errors
