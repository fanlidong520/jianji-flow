from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from jsonschema import ValidationError

from jianji_flow.contracts import validate_visual_selection
from jianji_flow.visual_candidates import (
    apply_visual_selections,
    build_visual_candidate_manifest,
    load_visual_selection,
    write_final_visual_selection_frames,
    write_visual_candidate_artifacts,
)


class FakeAsset:
    def __init__(self, asset_id: str, path: Path, duration_ms: int, sha256: str = "asset-sha") -> None:
        self.asset_id = asset_id
        self.path = path
        self.duration_ms = duration_ms
        self.sha256 = sha256


def _segments() -> list[dict]:
    return [
        {"id": "seg-001", "role": "hook", "start_ms": 0, "end_ms": 2000, "caption": "开头"},
        {"id": "seg-002", "role": "pain", "start_ms": 2000, "end_ms": 5000, "caption": "痛点"},
    ]


def _assets(tmp_path: Path) -> list[FakeAsset]:
    return [
        FakeAsset("asset-a", tmp_path / "IMG_001.mp4", 6000, "sha-a"),
        FakeAsset("asset-b", tmp_path / "IMG_002.mp4", 6000, "sha-b"),
        FakeAsset("asset-short", tmp_path / "IMG_003.mp4", 1000, "sha-short"),
    ]


def _matches() -> dict:
    return {
        "version": "0.1",
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "status": "selected",
                "asset_id": "asset-a",
                "source_path": "IMG_001.mp4",
                "source_start_ms": 0,
                "source_end_ms": 2000,
                "asset_duration_ms": 6000,
                "confidence": 0.55,
                "scores": {"filename": 0.55},
                "candidates": [],
                "evidence": ["fallback:first-available"],
            },
            {
                "id": "match-002",
                "segment_id": "seg-002",
                "status": "selected",
                "asset_id": "asset-b",
                "source_path": "IMG_002.mp4",
                "source_start_ms": 0,
                "source_end_ms": 3000,
                "asset_duration_ms": 6000,
                "confidence": 0.55,
                "scores": {"filename": 0.55},
                "candidates": [],
                "evidence": ["fallback:first-available"],
            },
        ],
    }


def _candidate_manifest(tmp_path: Path) -> dict:
    return {
        "version": "0.1",
        "asset_root": tmp_path.as_posix(),
        "candidates": [
            {
                "candidate_id": "seg-001-candidate-01",
                "segment_id": "seg-001",
                "asset_id": "asset-b",
                "asset_path": (tmp_path / "IMG_002.mp4").as_posix(),
                "asset_sha256": "sha-b",
                "asset_duration_ms": 6000,
                "source_start_ms": 3000,
                "source_end_ms": 5000,
                "available": True,
                "frames": [
                    {
                        "path": "visual-candidates/seg-001-candidate-01-01.png",
                        "time_ms": 3500,
                        "sha256": "frame-sha-1",
                    },
                    {
                        "path": "visual-candidates/seg-001-candidate-01-02.png",
                        "time_ms": 4000,
                        "sha256": "frame-sha-2",
                    },
                    {
                        "path": "visual-candidates/seg-001-candidate-01-03.png",
                        "time_ms": 4500,
                        "sha256": "frame-sha-3",
                    },
                ],
                "quality": {"frame_information": 0.2, "is_semantic": False},
                "warnings": [],
            }
        ],
    }


def test_visual_selection_contract_rejects_blank_candidate_and_reason():
    with pytest.raises(ValidationError):
        validate_visual_selection(
            {
                "version": "0.1",
                "candidate_manifest": "visual-candidates.json",
                "selections": {"seg-001": {"candidate_id": "", "reviewer": "codex-vision", "reason": ""}},
            }
        )


def test_candidate_manifest_ignores_filename_roles_and_bounds_windows(tmp_path: Path):
    manifest = build_visual_candidate_manifest(_segments(), _assets(tmp_path), tmp_path / "work")

    assert manifest["version"] == "0.1"
    assert manifest["candidates"]
    assert all(item["asset_path"].endswith(("IMG_001.mp4", "IMG_002.mp4")) for item in manifest["candidates"])
    assert all(item["source_end_ms"] - item["source_start_ms"] == item["segment_duration_ms"] for item in manifest["candidates"])
    assert all(item["source_end_ms"] <= item["asset_duration_ms"] for item in manifest["candidates"])
    assert not any("filename" in reason.lower() for item in manifest["candidates"] for reason in item.get("reasons", []))


def test_candidate_artifacts_record_frame_hashes_and_nonsemantic_quality(tmp_path: Path, monkeypatch):
    manifest = _candidate_manifest(tmp_path)
    frames_dir = tmp_path / "visual-candidates"

    def fake_extract(video_path: Path, frame_path: Path, time_ms: int) -> None:
        Image.new("RGB", (64, 64), (time_ms % 255, 20, 30)).save(frame_path)

    monkeypatch.setattr("jianji_flow.visual_candidates._extract_frame", fake_extract)
    outputs = write_visual_candidate_artifacts(manifest, _segments(), tmp_path / "work")

    assert Path(outputs["visual_candidate_sheet"]).exists()
    assert Path(outputs["visual_selection_template"]).exists()
    candidate = manifest["candidates"][0]
    assert len(candidate["frames"]) == 3
    for frame in candidate["frames"]:
        frame_path = tmp_path / "work" / frame["path"]
        assert frame_path.exists()
        assert frame["sha256"] == hashlib.sha256(frame_path.read_bytes()).hexdigest()
    assert candidate["quality"]["is_semantic"] is False


def test_load_visual_selection_validates_schema(tmp_path: Path):
    path = tmp_path / "visual-selections.json"
    path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "candidate_manifest": "visual-candidates.json",
                "selections": {
                    "seg-001": {
                        "candidate_id": "seg-001-candidate-01",
                        "reviewer": "codex-vision",
                        "reason": "画面展示了使用过程，支持开头文案。",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert load_visual_selection(path)["selections"]["seg-001"]["candidate_id"] == "seg-001-candidate-01"


def test_apply_visual_selection_updates_window_and_records_evidence(tmp_path: Path):
    selected = {
        "version": "0.1",
        "candidate_manifest": "visual-candidates.json",
        "selections": {
            "seg-001": {
                "candidate_id": "seg-001-candidate-01",
                "reviewer": "codex-vision",
                "reason": "画面展示了使用过程，支持开头文案。",
            }
        },
    }
    updated = apply_visual_selections(
        _segments(),
        _matches(),
        _assets(tmp_path),
        selected,
        _candidate_manifest(tmp_path),
    )

    match = next(item for item in updated["matches"] if item["segment_id"] == "seg-001")
    assert match["asset_id"] == "asset-b"
    assert match["source_start_ms"] == 3000
    assert match["source_end_ms"] == 5000
    assert "visual-review:seg-001-candidate-01" in match["evidence"]
    assert match["candidates"] == [
        {
            "asset_id": "asset-b",
            "source_path": (tmp_path / "IMG_002.mp4").as_posix(),
            "source_start_ms": 3000,
            "source_end_ms": 5000,
            "asset_duration_ms": 6000,
            "score": 1.0,
            "evidence": ["visual-review:seg-001-candidate-01"],
        }
    ]


def test_apply_visual_selection_rejects_stale_caption_metadata(tmp_path: Path):
    selected = {
        "version": "0.1",
        "candidate_manifest": "visual-candidates.json",
        "selections": {
            "seg-001": {
                "role": "hook",
                "caption": "A different script",
                "candidate_id": "seg-001-candidate-01",
                "reviewer": "codex-vision",
                "reason": "The selected frame supports the current beat.",
            }
        },
    }

    with pytest.raises(ValueError, match="caption changed"):
        apply_visual_selections(_segments(), _matches(), _assets(tmp_path), selected, _candidate_manifest(tmp_path))


def test_apply_visual_selection_rejects_stale_role_metadata(tmp_path: Path):
    selected = {
        "version": "0.1",
        "candidate_manifest": "visual-candidates.json",
        "selections": {
            "seg-001": {
                "role": "cta",
                "caption": "寮€澶?",
                "candidate_id": "seg-001-candidate-01",
                "reviewer": "codex-vision",
                "reason": "The selected frame supports the current beat.",
            }
        },
    }

    with pytest.raises(ValueError, match="role changed"):
        apply_visual_selections(_segments(), _matches(), _assets(tmp_path), selected, _candidate_manifest(tmp_path))


def test_apply_visual_selection_rejects_stale_candidate_story_metadata(tmp_path: Path):
    manifest = _candidate_manifest(tmp_path)
    manifest["candidates"][0]["role"] = "hook"
    manifest["candidates"][0]["caption"] = "A previous caption"
    selected = {
        "version": "0.1",
        "candidate_manifest": "visual-candidates.json",
        "selections": {
            "seg-001": {
                "candidate_id": "seg-001-candidate-01",
                "reviewer": "codex-vision",
                "reason": "The selected frame supports the current beat.",
            }
        },
    }

    with pytest.raises(ValueError, match="candidate caption changed"):
        apply_visual_selections(_segments(), _matches(), _assets(tmp_path), selected, manifest)


def test_write_final_visual_selection_frames_uses_retimed_match_range(tmp_path: Path, monkeypatch):
    source = tmp_path / "IMG_001.mp4"
    source.write_bytes(b"video")
    review_data = {
        "selections": [
            {
                "segment_id": "seg-001",
                "frames": ["candidate-1.png"],
            }
        ]
    }
    matches = {
        "matches": [
            {
                "segment_id": "seg-001",
                "status": "selected",
                "source_path": str(source),
                "source_start_ms": 1000,
                "source_end_ms": 2000,
            }
        ]
    }
    captured_times = []

    def fake_extract(_video_path: Path, frame_path: Path, time_ms: int) -> None:
        captured_times.append(time_ms)
        Image.new("RGB", (32, 32), "#f97316").save(frame_path)

    monkeypatch.setattr("jianji_flow.visual_candidates._extract_frame", fake_extract)

    updated = write_final_visual_selection_frames(review_data, matches, tmp_path / "work")

    assert captured_times == [1250, 1500, 1750]
    assert updated["selections"][0]["final_source_range"] == "1000-2000ms"
    assert len(updated["selections"][0]["final_frames"]) == 3
    assert all(Path(path).exists() for path in updated["selections"][0]["final_frames"])


def test_apply_visual_selection_rejects_unknown_candidate_before_render(tmp_path: Path):
    selected = {
        "version": "0.1",
        "candidate_manifest": "visual-candidates.json",
        "selections": {
            "seg-001": {
                "candidate_id": "seg-001-candidate-404",
                "reviewer": "codex-vision",
                "reason": "看过候选画面。",
            }
        },
    }

    with pytest.raises(ValueError, match="candidate.*not found"):
        apply_visual_selections(_segments(), _matches(), _assets(tmp_path), selected, _candidate_manifest(tmp_path))


def test_apply_visual_selection_rejects_cross_segment_candidate(tmp_path: Path):
    manifest = _candidate_manifest(tmp_path)
    manifest["candidates"][0]["segment_id"] = "seg-002"
    selected = {
        "version": "0.1",
        "candidate_manifest": "visual-candidates.json",
        "selections": {
            "seg-001": {
                "candidate_id": "seg-001-candidate-01",
                "reviewer": "codex-vision",
                "reason": "看过候选画面。",
            }
        },
    }

    with pytest.raises(ValueError, match="belongs to segment"):
        apply_visual_selections(_segments(), _matches(), _assets(tmp_path), selected, manifest)


def test_apply_visual_selection_rejects_stale_asset_fingerprint(tmp_path: Path):
    manifest = _candidate_manifest(tmp_path)
    manifest["candidates"][0]["asset_sha256"] = "old-sha"
    selected = {
        "version": "0.1",
        "candidate_manifest": "visual-candidates.json",
        "selections": {
            "seg-001": {
                "candidate_id": "seg-001-candidate-01",
                "reviewer": "codex-vision",
                "reason": "看过候选画面。",
            }
        },
    }

    with pytest.raises(ValueError, match="fingerprint"):
        apply_visual_selections(_segments(), _matches(), _assets(tmp_path), selected, manifest)


def test_apply_visual_selection_rejects_stale_frame_evidence(tmp_path: Path):
    manifest = _candidate_manifest(tmp_path)
    manifest["generated_in"] = (tmp_path / "board").as_posix()
    board = tmp_path / "board"
    for frame in manifest["candidates"][0]["frames"]:
        frame_path = board / frame["path"]
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        frame_path.write_bytes(frame["path"].encode("utf-8"))
        frame["sha256"] = hashlib.sha256(frame_path.read_bytes()).hexdigest()
    first_frame = board / manifest["candidates"][0]["frames"][0]["path"]
    first_frame.write_bytes(b"changed after review")
    selected = {
        "version": "0.1",
        "candidate_manifest": "visual-candidates.json",
        "selections": {
            "seg-001": {
                "candidate_id": "seg-001-candidate-01",
                "reviewer": "codex-vision",
                "reason": "看过候选画面。",
            }
        },
    }

    with pytest.raises(ValueError, match="frame fingerprint"):
        apply_visual_selections(_segments(), _matches(), _assets(tmp_path), selected, manifest)
