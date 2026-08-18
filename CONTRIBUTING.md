# Contributing

Thanks for improving `jianji-flow`.

Please keep contributions as small, focused changes. This project is intentionally narrow: auditable automatic preview-video workflows before full editor features.

## Local Checks

Run these before opening a pull request:

```powershell
python -m pytest -q
python scripts/run_smoke.py
python scripts/run_p0.py
```

`run_smoke.py` and `run_p0.py` generate a small test WAV, so they do not depend
on a developer machine having a Chinese TTS voice. For a real first-time trial,
use [`docs/validation/outside-user-trial.md`](docs/validation/outside-user-trial.md);
the normal `auto` provider uses Windows SAPI or the optional `edge-tts` backend.
GitHub CI runs the unit test suite only.

## Change Guidelines

- Add or update tests for behavior changes.
- Keep generated media out of commits.
- Do not commit generated outputs from `out/`, `work/`, or generated fixtures.
- Keep safety checks explicit and reviewable.
- Document user-facing behavior in `README.md` or `SKILL.md`.

## Pull Request Checklist

- Tests pass locally.
- The change does not copy reference video picture or audio into `remix.mp4`.
- Failure paths do not leave stale success artifacts.
- `review.md` reports uncertainty honestly.

Do not commit generated outputs unless a maintainer explicitly asks for a small fixture.
