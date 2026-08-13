from pathlib import Path

from PIL import Image

from jianji_flow.candidate_review import write_candidate_review


def _save_frame(path: Path, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 36), color).save(path)


def test_write_candidate_review_shows_current_and_recommended_candidate_frames(tmp_path: Path, monkeypatch):
    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        _save_frame(frame_path, "red" if "current" in video_path.name else "green")

    monkeypatch.setattr("jianji_flow.candidate_review._extract_frame", fake_extract_frame)
    recipe = {
        "segments": [
            {
                "id": "seg-003",
                "role": "feature",
                "match_id": "match-003",
                "caption": "Show the collapsible storage detail",
                "start_ms": 2000,
                "end_ms": 3600,
            }
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-003",
                "segment_id": "seg-003",
                "source_path": str(tmp_path / "current-feature.mp4"),
                "source_start_ms": 1000,
                "source_end_ms": 2600,
            }
        ]
    }
    fixes = {
        "segments": {
            "seg-003": {
                "role": "feature",
                "caption": "Show the collapsible storage detail",
                "reason": "weak story evidence",
                "current_asset_path": str(tmp_path / "current-feature.mp4"),
                "recommended_asset_path": str(tmp_path / "better-feature.mp4"),
                "recommendation_status": "recommended",
                "recommendation_warnings": [],
                "candidate_assets": [
                    {
                        "asset_path": str(tmp_path / "better-feature.mp4"),
                        "score": 80,
                        "reasons": ["matches role feature", "visually distinct from current segment"],
                        "warnings": [],
                        "role_match": True,
                    }
                ],
            }
        }
    }

    result = write_candidate_review(
        recipe,
        matches,
        fixes,
        tmp_path / "candidate-review.html",
        frames_dir=tmp_path / "candidate-frames",
    )

    html = (tmp_path / "candidate-review.html").read_text(encoding="utf-8")
    assert result["candidate_review"] == (tmp_path / "candidate-review.html").as_posix()
    assert result["candidate_frames"] == (tmp_path / "candidate-frames").as_posix()
    assert "Candidate Review" in html
    assert "seg-003" in html
    assert "Current segment" in html
    assert "Recommended candidate" in html
    assert "Show the collapsible storage detail" in html
    assert "visually distinct from current segment" in html
    assert 'src="candidate-frames/seg-003-current.png"' in html
    assert 'src="candidate-frames/seg-003-candidate-001.png"' in html
    assert (tmp_path / "candidate-frames" / "seg-003-current.png").exists()
    assert (tmp_path / "candidate-frames" / "seg-003-candidate-001.png").exists()


def test_write_candidate_review_continues_when_candidate_frame_extraction_fails(tmp_path: Path, monkeypatch):
    def fake_extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
        if "bad" in video_path.name:
            raise RuntimeError("cannot decode frame")
        _save_frame(frame_path, "blue")

    monkeypatch.setattr("jianji_flow.candidate_review._extract_frame", fake_extract_frame)
    recipe = {
        "segments": [
            {
                "id": "seg-001",
                "role": "hook",
                "match_id": "match-001",
                "caption": "Open with the messy drawer",
                "start_ms": 0,
                "end_ms": 1200,
            }
        ]
    }
    matches = {
        "matches": [
            {
                "id": "match-001",
                "segment_id": "seg-001",
                "source_path": str(tmp_path / "current-hook.mp4"),
                "source_start_ms": 0,
                "source_end_ms": 1200,
            }
        ]
    }
    fixes = {
        "segments": {
            "seg-001": {
                "role": "hook",
                "caption": "Open with the messy drawer",
                "reason": "weak story evidence",
                "current_asset_path": str(tmp_path / "current-hook.mp4"),
                "recommended_asset_path": str(tmp_path / "bad-hook.mp4"),
                "recommendation_status": "best_available_with_warnings",
                "recommendation_warnings": ["visual similarity check failed"],
                "candidate_assets": [
                    {
                        "asset_path": str(tmp_path / "bad-hook.mp4"),
                        "score": 10,
                        "reasons": ["matches role hook"],
                        "warnings": ["visual similarity check failed"],
                        "role_match": True,
                    }
                ],
            }
        }
    }

    write_candidate_review(
        recipe,
        matches,
        fixes,
        tmp_path / "candidate-review.html",
        frames_dir=tmp_path / "candidate-frames",
    )

    html = (tmp_path / "candidate-review.html").read_text(encoding="utf-8")
    assert "Frame unavailable" in html
    assert "cannot decode frame" in html
    assert "visual similarity check failed" in html
    assert (tmp_path / "candidate-frames" / "seg-001-current.png").exists()
