---
name: jianji-flow
description: Create auditable preview videos from a reference video, a local asset directory, and optional script text; outputs diagnosis.md, manifest.json, recipe.json, matches.json, captions.srt, captions.ass, voiceover.wav, remix.mp4, contact-sheet.png, optional shot-contact-sheet.png, reference-comparison.png, optional shot-plan.json, visual candidate evidence, candidate-review.html, fixes.template.json, review.md, and review.html after validation.
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

For product `quick`, report `diagnosis.md` even when the run continues; it starts as a filename/duration screening report and appends duplicate-media, source-diversity, and source-preflight warnings or failures when selected source frames look risky. It is not proof of visual correctness.
In `diagnosis.md`, use `CANDIDATE` for filename/duration-ready clips. Do not call those clips `READY`; that wording overstates visual understanding.
If the user runs `quick` without `--script`, say the default script is only for
cleaning-style home-product examples and contains five short story beats; other products need their own script.

Detailed workflow:

1. Run the environment check.
2. Generate synthetic fixtures only when the user wants a demo run.
3. Scan the local asset directory and create `manifest.json`.
4. For product quick runs, write `diagnosis.md`; stop if required material roles are missing.
5. If filenames are opaque or the first rough cut is weak, run `visual-review` and inspect `visual-candidate-sheet.png` with Codex vision; Codex writes a selection JSON with candidate ids and reasons for genuinely supported segments, then passes it with `--visual-selections`. Do not ask the user to edit JSON.
6. Build the segment plan and create `matches.json` and `recipe.json`.
7. Run JSON Schema validation and semantic validation.
8. Stop before rendering if validation has any blocking failure.
9. Run source preflight on selected source frames; append warnings/failures to product quick `diagnosis.md` when present, and stop before voiceover/render if severe residue or repeated independent evidence is detected. Do not count the same sampled risk again merely because one source video is reused across timeline segments.
10. Write `captions.srt` and `captions.ass`.
11. Generate `voiceover.wav` with local machine TTS.
12. Render `remix.mp4` only from validated manifest assets, burned-in captions, and generated voiceover.
13. Write `contact-sheet.png` with one frame per segment and `reference-comparison.png` with the same number of relative storyboard samples from the reference and remix.
14. Write `fixes.template.json` for weak or low-confidence segments, including same-role visual-similarity checks for repair recommendations.
15. Write `candidate-review.html` and `candidate-frames/` so current weak-segment frames can be compared with visible repair candidates.
16. When `--visual-selections`, `--fixes`, or `--apply-recommendation` is used, write the corresponding visual evidence or `Change report` and diagnostics.
17. When the user requests more visible pacing, pass `--multi-shot` after visual selection. It detects only bounded structural scene changes inside selected windows, flattens safe ranges into the final timeline, writes `shot-plan.json` after voiceover retiming, and writes `shot-contact-sheet.png` with one labeled frame per final shot. Low-confidence matches stay as one source window until visual review confirms them. Keep the result review-required until the rendered pacing is inspected.
18. Write `review.md` and `review.html` with pass, warning, fail status, `Story support`, a per-segment `Storyboard`, optional `Visual selection`, optional `Shot plan`, optional `Change report`, candidate-review link, and visual-similarity diagnostics when present.

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
- Treat `DUPLICATE MEDIA` and `SIMILAR MEDIA` as material-risk evidence, not proof that every file came from the same mother video; inspect the listed diagnostics and source frames.
- Do not call weak `Story support` usable; tell the user to confirm hook, pain, feature, evidence, and CTA in `contact-sheet.png`.
- Do not hide source-platform residue with a full-frame dark mask; rely on crop where appropriate and keep source-preflight warnings visible.
- Do not treat `visual-candidate-sheet.png` or a Codex visual selection as automatic semantic truth; it is explicit model-assisted review evidence and must remain auditable.
- A visual selection is tied to the candidate board's role and caption metadata. If the script changes, create a fresh `visual-review` board; stale selections are rejected before rendering. A missing candidate sheet is also a blocking input error, not a reason to emit a broken review link.
- When a visual selection is applied, preserve its full source window across voiceover retiming with the recorded bounded playback rate; do not silently trim the visually reviewed content.
- Do not fill or apply a candidate selection when the frames do not genuinely support the segment caption; partial selection is allowed and should remain `warning` when story evidence is incomplete.
- Do not silently ignore filled fixes entries. Unknown segment/role targets, missing replacement paths, and too-short clips must fail clearly.
- Do not present a risky replacement as clean. If `recommendation_status` is `best_available_with_warnings`, report the warning before suggesting the fix.
- Do not auto-apply a visually similar or visually unchecked recommendation. Treat `visually similar to current segment` and `visual similarity check failed` as review-required warnings.
- Do not treat `candidate-review.html` as proof of semantic visual matching. It is a human-facing evidence page for current frames, candidates, reasons, and warnings.
- Do not use scene boundaries to make a low-confidence match look more trustworthy. Keep it as one source window and report `skipped_low_confidence` in the shot plan.
- Treat an identical adjacent source shot sequence as a publish-blocking review warning; inspect the shot contact sheet and choose distinct footage when the repetition is not intentional.
- Do not present same-source-window candidates as clean improvements. They may expose a better time window inside a long file, but they require manual review before use.
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

Paced multi-shot draft after visual selection:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --visual-selections out\visual-board\visual-selections.json --multi-shot --work-dir out\visual-selected-multi-shot
```

Rerun with a segment repair file:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --fixes out\jianji-flow-quick\fixes.template.json
```

Apply one clean recommendation from a repair file:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --fixes out\jianji-flow-quick\fixes.template.json --apply-recommendation seg-003
```

Visual candidate board and selected rerun:

```powershell
jianji-flow visual-review --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --work-dir out\visual-board
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --visual-selections out\visual-board\visual-selections.json --work-dir out\visual-selected
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
- `shot-contact-sheet.png` when `--multi-shot` is used
- `reference-comparison.png`
- `shot-plan.json` when `--multi-shot` is used
- `candidate-review.html`
- `candidate-frames/`
- `visual-candidates.json`, `visual-candidate-sheet.png`, and `visual-selection.template.json` when `visual-review` is used
- `visual-selection-evidence/` when `--visual-selections` is used
- `fixes.template.json`
- `visual-similarity-diagnostics` when listed in `review.md`
- `change-diagnostics` when a fix run lists a `Change report`
- `review.md`
- `review.html`

On fail, report `review.md` and any diagnostic files that were written, including `source-diagnostics` or preserved `contact-sheet.png`.
Never describe a failed or warning run as completed video output.

## Review Status Language

- `pass`: generated a reviewable rough cut; still ask the user to inspect before publishing.
- `warning`: generated artifacts only for manual review; do not imply the video is usable yet.
- `fail`: blocking issue; do not point to stale success artifacts as output.

If `Story support` is `weak`, report its `next_action` exactly. Explain that the named roles lack non-filename visual evidence, then inspect `contact-sheet.png` and `reference-comparison.png` yourself. Do not ask the user to edit JSON. If a repair is needed, Codex should choose a genuinely appropriate candidate, write the repair file, rerun, and then check `Change report` before comparing the same segment in the new `contact-sheet.png`.
If `review.md` lists `visual_similarity_diagnostics`, explain that the folder contains sampled frames used to downgrade duplicate-looking or unchecked recommendations. Do not describe those checks as semantic understanding.
If `review.md` lists a `Change report`, use it before discussing JSON: it names the changed segment, before/after asset, before/after source range, before/after sampled frames, `Picture change`, sampling note, and override reason. Explain that `Picture change` means sampled frames differ; it is not proof that the new shot fits the script.
Use the `Storyboard` section before discussing JSON: it is the fastest way to see each segment's caption, selected asset, source range, evidence, and risk.
Use the `Visual selection` section when present: it lists the reviewer, candidate id, reason, and selected frames. Treat it as inspectable evidence, not proof that the product claim is accurate.
Use the `Shot plan` section when present: it lists the final retimed source boundaries and fallback status. Open `shot-contact-sheet.png` to inspect one frame per final shot. Scene boundaries prove only structural cutting, not semantic support for the script.
If the shot plan lists `skipped_low_confidence` or an adjacent repeated shot sequence, report that warning before discussing pacing quality. Do not call the multi-shot pass clean until the repeated footage is intentionally accepted or replaced.
Use `candidate-review.html` before suggesting a fix: it is the fastest way to show what the current segment looks like, what candidate frames are available, and whether warnings make the candidate manual-review only.
