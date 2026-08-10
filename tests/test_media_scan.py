import hashlib
import json
from pathlib import Path

import pytest

from jianji_flow.contracts import validate_manifest
from jianji_flow.media_probe import MediaInfo
from jianji_flow.media_scan import scan_assets, write_manifest


def _fake_probe(path: Path) -> MediaInfo:
    return MediaInfo(
        source_path=str(path),
        duration_ms=3000,
        width=1080,
        height=1920,
        fps=30.0,
        has_audio=path.suffix.lower() in {".mp4", ".mov", ".m4v"},
        rotation=0,
    )


def test_scan_ignores_unsupported_files_and_recurses_in_sorted_order(tmp_path, monkeypatch):
    nested = tmp_path / "b" / "nested"
    nested.mkdir(parents=True)
    (tmp_path / "z.mp4").write_bytes(b"z")
    (tmp_path / "a.png").write_bytes(b"a")
    (nested / "m.mov").write_bytes(b"m")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "no_extension").write_bytes(b"ignore")
    monkeypatch.setattr("jianji_flow.media_scan.probe_for_scan", _fake_probe)

    records = scan_assets(tmp_path)

    assert [record.path.relative_to(tmp_path).as_posix() for record in records] == [
        "b/nested/m.mov",
        "z.mp4",
    ]
    assert all(record.media_type == "video" for record in records)


def test_sha256_and_asset_id_are_stable_for_same_relative_path_and_content(tmp_path, monkeypatch):
    asset = tmp_path / "Clip.MP4"
    asset.write_bytes(b"same bytes")
    monkeypatch.setattr("jianji_flow.media_scan.probe_for_scan", _fake_probe)

    first = scan_assets(tmp_path)[0]
    second = scan_assets(tmp_path)[0]

    assert first.sha256 == hashlib.sha256(b"same bytes").hexdigest()
    assert first.asset_id == second.asset_id
    assert first.asset_id
    assert first.path == asset


def test_damaged_media_is_skipped_with_a_clear_error(tmp_path, monkeypatch):
    good = tmp_path / "good.mp4"
    damaged = tmp_path / "damaged.mp4"
    good.write_bytes(b"good")
    damaged.write_bytes(b"bad")

    def fake_probe(path: Path):
        if path == damaged:
            raise RuntimeError("ffprobe failed: invalid data")
        return _fake_probe(path)

    monkeypatch.setattr("jianji_flow.media_scan.probe_for_scan", fake_probe)
    errors = []

    records = scan_assets(tmp_path, errors=errors)

    assert [record.path.name for record in records] == ["good.mp4"]
    assert len(errors) == 1
    assert "damaged.mp4" in errors[0]
    assert "invalid data" in errors[0]


def test_write_manifest_outputs_schema_valid_json(tmp_path, monkeypatch):
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    asset = asset_root / "clip.mp4"
    asset.write_bytes(b"clip")
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"reference")
    monkeypatch.setattr("jianji_flow.media_scan.probe_for_scan", _fake_probe)
    records = scan_assets(asset_root)
    output = tmp_path / "manifest.json"

    write_manifest(records, output, asset_root=asset_root, reference_path=reference)

    data = json.loads(output.read_text(encoding="utf-8"))
    validate_manifest(data)
    assert data["asset_root"] == str(asset_root)
    assert data["reference"] == str(reference)
    assert data["assets"][0]["path"] == str(asset)


def test_write_manifest_rejects_empty_records(tmp_path):
    with pytest.raises(ValueError, match="at least one asset"):
        write_manifest(
            [],
            tmp_path / "manifest.json",
            asset_root=tmp_path / "assets",
            reference_path=tmp_path / "reference.mp4",
        )
