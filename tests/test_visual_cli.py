from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from jianji_flow import cli
from jianji_flow.media_probe import MediaInfo
from jianji_flow.media_scan import AssetRecord


def _asset(tmp_path: Path) -> AssetRecord:
    return AssetRecord(
        asset_id="asset-001",
        path=tmp_path / "IMG_001.mp4",
        sha256="sha-001",
        media_type="video",
        duration_ms=6000,
        width=592,
        height=1280,
        fps=30.0,
        has_audio=True,
    )


def test_parser_accepts_visual_selection_inputs_and_board_command():
    parser = cli._build_parser()

    run_args = parser.parse_args(
        [
            "run",
            "--mode",
            "product",
            "--reference",
            "reference.mp4",
            "--assets",
            "assets",
            "--work-dir",
            "work",
            "--visual-selections",
            "visual-selections.json",
        ]
    )
    board_args = parser.parse_args(
        [
            "visual-review",
            "--reference",
            "reference.mp4",
            "--assets",
            "assets",
            "--work-dir",
            "work",
        ]
    )

    assert run_args.visual_selections == "visual-selections.json"
    assert board_args.command == "visual-review"


def test_visual_review_command_writes_candidate_board(tmp_path: Path, monkeypatch):
    reference = tmp_path / "reference.mp4"
    assets = tmp_path / "assets"
    work_dir = tmp_path / "work"
    reference.write_bytes(b"reference")
    assets.mkdir()
    record = _asset(assets)

    monkeypatch.setattr(cli, "resolve_existing_file", lambda value: reference)
    monkeypatch.setattr(cli, "resolve_existing_dir", lambda value: assets)
    monkeypatch.setattr(
        cli,
        "run_ffprobe",
        lambda value: MediaInfo(reference.as_posix(), 6000, 592, 1280, 30.0, True, 0),
    )
    monkeypatch.setattr(cli, "scan_assets", lambda value: [record])
    monkeypatch.setattr(
        cli,
        "write_visual_candidate_artifacts",
        lambda manifest, segments, output: {
            "visual_candidate_manifest": (output / "visual-candidates.json").as_posix(),
            "visual_candidate_sheet": (output / "visual-candidate-sheet.png").as_posix(),
            "visual_selection_template": (output / "visual-selection.template.json").as_posix(),
        },
    )

    result = cli.main(
        [
            "visual-review",
            "--reference",
            reference.as_posix(),
            "--assets",
            assets.as_posix(),
            "--work-dir",
            work_dir.as_posix(),
        ]
    )

    assert result == 0


def test_quick_does_not_stop_for_missing_filename_roles_when_visual_selection_exists(tmp_path: Path, monkeypatch):
    reference = tmp_path / "reference.mp4"
    assets = tmp_path / "assets"
    work_dir = tmp_path / "work"
    selection_path = tmp_path / "visual-selections.json"
    reference.write_bytes(b"reference")
    assets.mkdir()
    selection_path.write_text("{}", encoding="utf-8")
    record = _asset(assets)
    calls: list[Namespace] = []

    monkeypatch.setattr(cli, "resolve_existing_file", lambda value: reference)
    monkeypatch.setattr(cli, "resolve_existing_dir", lambda value: assets)
    monkeypatch.setattr(
        cli,
        "run_ffprobe",
        lambda value: MediaInfo(reference.as_posix(), 6000, 592, 1280, 30.0, True, 0),
    )
    monkeypatch.setattr(cli, "scan_assets", lambda value: [record])
    monkeypatch.setattr(
        cli,
        "diagnose_product_assets",
        lambda records, segments: {"status": "fail", "roles": {}, "actions": []},
    )
    monkeypatch.setattr(cli, "_run_pipeline", lambda args, **kwargs: calls.append(args) or 0)

    result = cli.main(
        [
            "quick",
            "--reference",
            reference.as_posix(),
            "--assets",
            assets.as_posix(),
            "--work-dir",
            work_dir.as_posix(),
            "--visual-selections",
            selection_path.as_posix(),
        ]
    )

    assert result == 0
    assert calls and calls[0].visual_selections == selection_path.as_posix()


def test_materialize_visual_selection_requires_candidate_sheet(tmp_path: Path):
    manifest_path = tmp_path / "visual-candidates.json"
    manifest_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="visual candidate sheet missing"):
        cli._materialize_visual_selection_review_data(
            {"selections": {}},
            {"candidates": []},
            manifest_path,
            tmp_path / "work",
        )
