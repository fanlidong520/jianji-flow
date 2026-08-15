from pathlib import Path

from jianji_flow.source_diversity import diagnose_source_diversity


def _asset(
    path: str,
    *,
    duration_ms: int = 10_000,
    sha256: str = "hash",
    width: int = 592,
    height: int = 1280,
) -> dict:
    return {
        "path": Path(path).as_posix(),
        "duration_ms": duration_ms,
        "sha256": sha256,
        "width": width,
        "height": height,
    }


def test_diagnose_source_diversity_warns_on_similar_reencoded_candidates(tmp_path, monkeypatch):
    calls = []

    def fake_mean_frame_difference(left_path, right_path, *, duration_ms, diagnostics_dir, **kwargs):
        calls.append((left_path, right_path, duration_ms, diagnostics_dir))
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        return 1.5

    monkeypatch.setattr("jianji_flow.source_diversity.mean_frame_difference", fake_mean_frame_difference)

    result = diagnose_source_diversity(
        [
            _asset("01-source.mp4", sha256="original"),
            _asset("02-reencoded.mp4", sha256="reencoded", duration_ms=10_120),
        ],
        tmp_path / "source-diversity-diagnostics",
    )

    assert result["status"] == "warning"
    assert result["similar_groups"] == [
        {
            "paths": ["01-source.mp4", "02-reencoded.mp4"],
            "score": 1.5,
        }
    ]
    assert len(calls) == 1
    assert (tmp_path / "source-diversity-diagnostics").is_dir()


def test_diagnose_source_diversity_skips_exact_duplicates(tmp_path, monkeypatch):
    def forbidden_mean_frame_difference(*args, **kwargs):
        raise AssertionError("exact duplicates should be handled by sha256 diagnosis")

    monkeypatch.setattr("jianji_flow.source_diversity.mean_frame_difference", forbidden_mean_frame_difference)

    result = diagnose_source_diversity(
        [_asset("01-source.mp4", sha256="same"), _asset("02-copy.mp4", sha256="same")],
        tmp_path / "source-diversity-diagnostics",
    )

    assert result["status"] == "pass"
    assert result["similar_groups"] == []
    assert not (tmp_path / "source-diversity-diagnostics").exists()


def test_diagnose_source_diversity_skips_obviously_different_candidates(tmp_path, monkeypatch):
    def forbidden_mean_frame_difference(*args, **kwargs):
        raise AssertionError("different-sized or much-longer clips are not candidates")

    monkeypatch.setattr("jianji_flow.source_diversity.mean_frame_difference", forbidden_mean_frame_difference)

    result = diagnose_source_diversity(
        [
            _asset("01-source.mp4", sha256="one", duration_ms=10_000),
            _asset("02-longer.mp4", sha256="two", duration_ms=50_000),
            _asset("03-wide.mp4", sha256="three", width=1080, height=1920),
        ],
        tmp_path / "source-diversity-diagnostics",
    )

    assert result["status"] == "pass"
    assert result["similar_groups"] == []


def test_diagnose_source_diversity_warns_on_partial_mother_clip_overlap(tmp_path, monkeypatch):
    calls = []

    monkeypatch.setattr(
        "jianji_flow.source_diversity.mean_frame_difference",
        lambda *args, **kwargs: 20.0,
    )

    def fake_normalized_frame_overlap(left_path, right_path, **kwargs):
        calls.append((left_path, right_path, kwargs))
        return {"score": 1.2, "coverage": 0.67}

    monkeypatch.setattr("jianji_flow.source_diversity.normalized_frame_overlap", fake_normalized_frame_overlap)

    result = diagnose_source_diversity(
        [
            _asset("01-mother-clip.mp4", sha256="original", duration_ms=10_000),
            _asset("02-short-cut.mp4", sha256="cut", duration_ms=4_500),
        ],
        tmp_path / "source-diversity-diagnostics",
    )

    assert result["status"] == "warning"
    assert result["similar_groups"] == [
        {
            "paths": ["01-mother-clip.mp4", "02-short-cut.mp4"],
            "score": 1.2,
            "coverage": 0.67,
            "match_mode": "partial-overlap",
        }
    ]
    assert len(calls) == 1


def test_diagnose_source_diversity_ignores_low_partial_overlap_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.source_diversity.mean_frame_difference",
        lambda *args, **kwargs: 20.0,
    )
    monkeypatch.setattr(
        "jianji_flow.source_diversity.normalized_frame_overlap",
        lambda *args, **kwargs: {"score": 1.2, "coverage": 0.33},
    )

    result = diagnose_source_diversity(
        [
            _asset("01-scene-a.mp4", sha256="one", duration_ms=10_000),
            _asset("02-scene-b.mp4", sha256="two", duration_ms=4_500),
        ],
        tmp_path / "source-diversity-diagnostics",
    )

    assert result["status"] == "pass"
    assert result["similar_groups"] == []
