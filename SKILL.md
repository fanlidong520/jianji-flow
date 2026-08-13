---
name: jianji-flow
description: Create auditable preview videos from a reference video, a local asset directory, and optional script text; outputs diagnosis.md, manifest.json, recipe.json, matches.json, captions.srt, captions.ass, voiceover.wav, remix.mp4, contact-sheet.png, candidate-review.html, fixes.template.json, review.md, and review.html after validation.
---

# jianji-flow

Use this skill when the user wants an automatic local preview-video workflow.
Current versions create inspectable intermediate files, machine voiceover, burned-in captions, a playable MP4 preview, and a local review page.
It does not create Jianying, CapCut, or other editor draft projects.
Treat it as a local auditable rough-cut workflow, not as a full editor or a true viral-reference decomposition engine.
Treat `warning` as review-required output, not as publish-ready success.

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
3. `jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets`

For product `quick`, report `diagnosis.md` even when the run continues; it starts as a filename/duration screening report and appends source preflight warnings or failures when selected source frames look risky. It is not proof of visual correctness.
In `diagnosis.md`, use `CANDIDATE` for filename/duration-ready clips. Do not call those clips `READY`; that wording overstates visual understanding.
If the user runs `quick` without `--script`, say the default script is only for
cleaning-style home-product examples; other products need their own script.

Detailed workflow:

1. Run the environment check.
2. Generate synthetic fixtures only when the user wants a demo run.
3. Scan the local asset directory and create `manifest.json`.
4. For product quick runs, write `diagnosis.md`; stop if required material roles are missing.
5. Build the segment plan and create `matches.json` and `recipe.json`.
6. Run JSON Schema validation and semantic validation.
7. Stop before rendering if validation has any blocking failure.
8. Run source preflight on selected source frames; append warnings/failures to product quick `diagnosis.md` when present, and stop before voiceover/render if severe old subtitles or platform UI are detected.
9. Write `captions.srt` and `captions.ass`.
10. Generate `voiceover.wav` with local machine TTS.
11. Render `remix.mp4` only from validated manifest assets, burned-in captions, and generated voiceover.
12. Write `contact-sheet.png` with one frame per segment.
13. Write `fixes.template.json` for weak or low-confidence segments, including same-role visual-similarity checks for repair recommendations.
14. Write `candidate-review.html` and `candidate-frames/` so current weak-segment frames can be compared with visible repair candidates.
15. Write `review.md` and `review.html` with pass, warning, fail status, `Story support`, a per-segment `Storyboard`, candidate-review link, and visual-similarity diagnostics when present.

## Hard Rules

- Do not use reference video picture or audio in `remix.mp4`.
- Do not accept URL, protocol, protocol-relative, or network paths.
- Do not write outputs outside the requested work directory.
- Do not render a segment whose match is missing or rejected.
- Do not hide low-confidence matches; report them in `review.md`.
- Do not leave stale success artifacts after a failed rerun.
- Do not describe a run as publish-ready. `pass` still needs human review; `warning` means review-required rough cut only.
- Do not call a filename-only warning visually verified; tell the user it must be checked in `contact-sheet.png`.
- Do not describe `diagnosis.md` `CANDIDATE` clips as visually ready; they only passed pre-render filename/duration screening.
- Do not call weak `Story support` usable; tell the user to confirm hook, pain, feature, evidence, and CTA in `contact-sheet.png`.
- Do not silently ignore filled fixes entries. Unknown segment/role targets, missing replacement paths, and too-short clips must fail clearly.
- Do not present a risky replacement as clean. If `recommendation_status` is `best_available_with_warnings`, report the warning before suggesting the fix.
- Do not auto-apply a visually similar or visually unchecked recommendation. Treat `visually similar to current segment` and `visual similarity check failed` as review-required warnings.
- Do not treat `candidate-review.html` as proof of semantic visual matching. It is a human-facing evidence page for current frames, candidates, reasons, and warnings.
- Do not present wrong-role fallback candidates as recommendations. If `recommendation_status` is `no_candidate`, explain that no same-role replacement was found; fallback candidates are manual-inspection options only.
- Do not claim image support, music, effects, publishing, source-audio preservation, true reference decomposition, or editor draft export.

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

Rerun with a segment repair file:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --fixes out\jianji-flow-quick\fixes.template.json
```

Apply one clean recommendation from a repair file:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --fixes out\jianji-flow-quick\fixes.template.json --apply-recommendation seg-003
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
- `diagnosis.md` for product quick runs, including source preflight warnings or failures when found
- `recipe.json`
- `matches.json`
- `captions.srt`
- `captions.ass`
- `voiceover.wav`
- `remix.mp4`
- `contact-sheet.png`
- `candidate-review.html`
- `candidate-frames/`
- `fixes.template.json`
- `visual-similarity-diagnostics` when listed in `review.md`
- `review.md`
- `review.html`

On fail, report `review.md` and any diagnostic files that were written, including `source-diagnostics` or preserved `contact-sheet.png`.
Never describe a failed or warning run as completed video output.

## Review Status Language

- `pass`: generated a reviewable rough cut; still ask the user to inspect before publishing.
- `warning`: generated artifacts only for manual review; do not imply the video is usable yet.
- `fail`: blocking issue; do not point to stale success artifacts as output.

If `Story support` is `weak`, report its `next_action` exactly. Explain that the named roles lack non-filename visual evidence, then ask the user to replace or manually verify those clips in `contact-sheet.png`. If the user wants to repair one segment, point them to `fixes.template.json`: check `recommended_asset_path`, `recommendation_status`, `recommendation_warnings`, and `role_match`; use `--apply-recommendation SEGMENT_ID` only when the status is `recommended`; otherwise fill one `asset_path` manually only when the candidate is genuinely appropriate, rerun with `--fixes`, then compare the same segment in the new `contact-sheet.png`.
If `review.md` lists `visual_similarity_diagnostics`, explain that the folder contains sampled frames used to downgrade duplicate-looking or unchecked recommendations. Do not describe those checks as semantic understanding.
Use the `Storyboard` section before discussing JSON: it is the fastest way to see each segment's caption, selected asset, source range, evidence, and risk.
Use `candidate-review.html` before suggesting a fix: it is the fastest way to show what the current segment looks like, what candidate frames are available, and whether warnings make the candidate manual-review only.
