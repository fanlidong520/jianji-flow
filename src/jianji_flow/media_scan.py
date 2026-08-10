from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .contracts import validate_manifest
from .media_probe import MediaInfo, run_ffprobe


SUPPORTED_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v"})
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    path: Path
    sha256: str
    media_type: str
    duration_ms: int
    width: int
    height: int
    fps: float
    has_audio: bool


def probe_for_scan(path: Path) -> MediaInfo:
    return run_ffprobe(path)


def _normalized_relative_path(path: Path, asset_dir: Path) -> str:
    return path.relative_to(asset_dir).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe_value(info: MediaInfo | dict[str, Any], name: str) -> Any:
    if isinstance(info, dict):
        return info[name]
    return getattr(info, name)


def _asset_id(relative_path: str, digest: str) -> str:
    identity = f"{relative_path}\0{digest}".encode("utf-8")
    return f"asset-{hashlib.sha256(identity).hexdigest()}"


def scan_assets(asset_dir: Path, errors: list[str] | None = None) -> list[AssetRecord]:
    asset_dir = asset_dir.resolve()
    if not asset_dir.is_dir():
        raise NotADirectoryError(f"asset directory does not exist: {asset_dir}")

    records: list[AssetRecord] = []
    for path in sorted(
        (candidate for candidate in asset_dir.rglob("*") if candidate.is_file()),
        key=lambda candidate: (
            _normalized_relative_path(candidate, asset_dir).casefold(),
            _normalized_relative_path(candidate, asset_dir),
        ),
    ):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        relative_path = _normalized_relative_path(path, asset_dir)
        try:
            digest = _sha256(path)
            info = probe_for_scan(path)
            records.append(
                AssetRecord(
                    asset_id=_asset_id(relative_path, digest),
                    path=path,
                    sha256=digest,
                    media_type="video",
                    duration_ms=int(_probe_value(info, "duration_ms")),
                    width=int(_probe_value(info, "width")),
                    height=int(_probe_value(info, "height")),
                    fps=float(_probe_value(info, "fps")),
                    has_audio=bool(_probe_value(info, "has_audio")),
                )
            )
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            message = f"{path}: media probe failed: {exc}"
            LOGGER.warning(message)
            if errors is None:
                continue
            errors.append(message)

    return records


def _manifest_asset(record: AssetRecord) -> dict[str, Any]:
    data = asdict(record)
    data["path"] = str(record.path)
    return data


def write_manifest(
    records: list[AssetRecord],
    output_path: Path,
    *,
    asset_root: Path,
    reference_path: Path,
) -> None:
    if not records:
        raise ValueError("manifest requires at least one asset")

    manifest = {
        "version": "0.1",
        "asset_root": str(asset_root),
        "reference": str(reference_path),
        "assets": [_manifest_asset(record) for record in records],
    }
    validate_manifest(manifest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
