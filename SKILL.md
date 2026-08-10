---
name: jianji-flow
description: Create auditable preview videos from a reference video, a local asset directory, and optional script text; outputs manifest.json, recipe.json, matches.json, captions.srt, remix.mp4, and review.md after validation.
---

# jianji-flow

Use this skill when the user wants an automatic local preview-video workflow.
Version 0.1 creates inspectable intermediate files and a playable MP4 preview.
It does not create Jianying, CapCut, or other editor draft projects.

## Required Inputs

Ask for any missing input before running:

- Reference video path.
- Local asset directory path.
- Mode: `product` or `talking-head`.
- Work/output directory path.
- Optional script or transcript path.

## Workflow

1. Run the environment check.
2. Generate synthetic fixtures only when the user wants a demo run.
3. Scan the local asset directory and create `manifest.json`.
4. Build the segment plan and create `matches.json` and `recipe.json`.
5. Run JSON Schema validation and semantic validation.
6. Stop before rendering if validation has any blocking failure.
7. Write `captions.srt`.
8. Render `remix.mp4` only from validated manifest assets.
9. Write `review.md` with pass, warning, or fail status.

## Hard Rules

- Do not use reference video picture or audio in `remix.mp4`.
- Do not accept URL, protocol, protocol-relative, or network paths.
- Do not write outputs outside the requested work directory.
- Do not render a segment whose match is missing or rejected.
- Do not hide low-confidence matches; report them in `review.md`.
- Do not leave a stale `remix.mp4` after a failed rerun.
- Do not claim image support, TTS, music, effects, publishing, or editor draft export in v0.1.

## Commands

Environment:

```powershell
python scripts/check_env.py
```

Demo fixtures:

```powershell
python scripts/generate_fixtures.py --output fixtures
```

Product smoke:

```powershell
python -m jianji_flow run --mode product --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --work-dir out\scenario-a-product --target-width 320 --target-height 180 --target-fps 12
```

Talking-head smoke:

```powershell
python -m jianji_flow run --mode talking-head --reference fixtures\scenario-b-talking\reference.mp4 --assets fixtures\scenario-b-talking\assets --script fixtures\scenario-b-talking\transcript.txt --work-dir out\scenario-b-talking --target-width 320 --target-height 180 --target-fps 12
```

Regression:

```powershell
python scripts/run_smoke.py
python scripts/run_p0.py
python -m pytest -q
```

## Output Summary

On success or warning, report the paths for:

- `manifest.json`
- `recipe.json`
- `matches.json`
- `captions.srt`
- `remix.mp4`
- `review.md`

On fail, report `review.md` and any diagnostic JSON files that were written.
Never describe a failed run as completed video output.
