---
name: jianji-flow
description: Create auditable preview videos from a reference video, a local asset directory, and optional script text; outputs manifest.json, recipe.json, matches.json, captions.srt, captions.ass, voiceover.wav, remix.mp4, contact-sheet.png, review.md, and review.html after validation.
---

# jianji-flow

Use this skill when the user wants an automatic local preview-video workflow.
Version 0.2 creates inspectable intermediate files, machine voiceover, burned-in captions, a playable MP4 preview, and a local review page.
It does not create Jianying, CapCut, or other editor draft projects.

## Required Inputs

Ask for any missing input before running:

- Reference video path.
- Local asset directory path.
- Mode: `product` or `talking-head`.
- Work/output directory path.
- Optional script or transcript path.

## Workflow

For first-time users, prefer:

1. `jianji-flow doctor`
2. `jianji-flow demo`
3. `jianji-flow quick --reference examples\reference.mp4 --assets examples\assets`

If `quick` writes `diagnosis.md`, report the missing or weak material roles and
do not describe the run as a completed video.

Detailed workflow:

1. Run the environment check.
2. Generate synthetic fixtures only when the user wants a demo run.
3. Scan the local asset directory and create `manifest.json`.
4. Build the segment plan and create `matches.json` and `recipe.json`.
5. Run JSON Schema validation and semantic validation.
6. Stop before rendering if validation has any blocking failure.
7. Write `captions.srt` and `captions.ass`.
8. Generate `voiceover.wav` with local machine TTS.
9. Render `remix.mp4` only from validated manifest assets, burned-in captions, and generated voiceover.
10. Write `contact-sheet.png` with one frame per segment.
11. Write `review.md` and `review.html` with pass, warning, or fail status.

## Hard Rules

- Do not use reference video picture or audio in `remix.mp4`.
- Do not accept URL, protocol, protocol-relative, or network paths.
- Do not write outputs outside the requested work directory.
- Do not render a segment whose match is missing or rejected.
- Do not hide low-confidence matches; report them in `review.md`.
- Do not leave stale success artifacts after a failed rerun.
- Do not describe a run as successful unless `review.md` is pass or warning and the requested output artifacts exist.
- Do not claim image support, music, effects, publishing, source-audio preservation, or editor draft export in v0.2.

## Commands

Environment:

```powershell
python scripts/check_env.py
jianji-flow doctor
```

Demo fixtures:

```powershell
python scripts/generate_fixtures.py --output fixtures
jianji-flow demo
```

Quick home-product draft:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets
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
- `captions.ass`
- `voiceover.wav`
- `remix.mp4`
- `contact-sheet.png`
- `review.md`
- `review.html`

On fail, report `review.md` and any diagnostic JSON files that were written.
Never describe a failed run as completed video output.
