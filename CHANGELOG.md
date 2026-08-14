# Changelog

## Unreleased

- Planned v0.3 usability layer: `doctor`, `demo`, `quick`, material diagnosis,
  source preflight, and plain-language review summary.
- Added source preflight checks that stop before voiceover/render when selected
  source frames show severe old-subtitle or platform-UI residue.
- Added filename-only review warnings so role-labeled assembly is not reported
  as visually verified.
- Added `Story support` review diagnostics so role-labeled assembly without
  non-filename visual evidence becomes a warning instead of a false pass.
- Wrote `diagnosis.md` on successful product `quick` runs so material readiness
  remains visible before the user judges the rendered cut.
- Appended source preflight warnings and failures to product `quick`
  `diagnosis.md` so risky source frames are visible before judging the cut.
- Changed product `quick` material diagnosis wording from user-visible `READY`
  to `CANDIDATE` for filename/duration-ready clips, avoiding false visual
  certainty.
- Added stable non-zero source-window selection for longer matched clips while
  keeping `source-window` separate from visual evidence in review warnings.
- Added `source-preflight:clean` match evidence after clean source-frame sampling,
  while keeping it separate from product-story visual evidence.
- Added frame-information window scoring with auditable `window-diagnostics`
  frames, while keeping `window-score` separate from story-match evidence.
- Added `fixes.template.json` and `--fixes` so weak or low-confidence segments
  can be replaced one by one, with override evidence recorded in `matches.json`.
- Added scored repair-template recommendations with explicit warnings when the
  best available replacement would repeat an adjacent source.
- Changed initial matching to prefer a different adjacent source when another
  same-role asset is available, reducing voiceover-shell rough cuts.
- Changed repair recommendations so wrong-role fallback candidates are listed
  for manual inspection but are not presented as clean recommendations.
- Added repair recommendation conflict warnings when multiple weak segments
  would reuse the same replacement asset.
- Added conservative multi-shot handling that keeps low-confidence matches as
  one source window and warns when adjacent segments repeat the same shot
  sequence.
- Added a storyboard section to `review.md` and `review.html` so each segment's
  role, caption, source range, evidence, and risk can be checked without opening
  JSON files.
- Kept retimed `source-window` evidence synchronized with retimed source ranges
  so review pages do not show conflicting clip windows.
- Added `--apply-recommendation SEGMENT_ID` so a clean recommendation from
  `fixes.template.json` can be applied without manually editing JSON.
- Blocked automatic application of warned or missing repair recommendations.
- Added multi-frame visual similarity checks for same-role repair candidates so
  duplicate-looking replacement files are downgraded instead of being presented
  as clean recommendations.
- Added `visual-similarity-diagnostics` output when repair recommendation checks
  extract frames for audit.
- Added `candidate-review.html` and `candidate-frames/` so weak segments show
  current frames beside visible repair candidates, reasons, and warnings.
- Removed stale candidate-review artifacts on failed review runs so failed
  outputs do not look repair-ready.
- Added same-source alternate-window repair candidates with
  `recommended_source_start_ms`, while keeping them warning-only unless a user
  manually confirms the window.
- Added a fix-run `Change report` with before/after asset ranges, before/after
  sampled frames, picture-change scores, sampling notes, override reasons, and
  `change-diagnostics/` frames.
- Changed warning CLI output from `completed` to `review required` so review-only
  rough cuts are not mistaken for passed outputs.
- Added `reference-comparison.png` and embedded it in `review.html` so every run
  shows the same number of relative storyboard samples from the reference and remix side by side.
- Updated the visual-selection workflow so Codex performs the frame review and
  writes the selection JSON; users do not need to edit intermediate JSON files.
- Aligned source preflight with the renderer's crop-safe area so platform chrome
  that will never reach the remix is not reported as a visible-frame risk.
- Added opt-in `--multi-shot` scene-boundary detection that flattens selected
  source windows into bounded short shots and writes a final retimed `shot-plan.json`.
- Added multi-shot schema, semantic path/duration checks, renderer flattening,
  and review-page evidence without changing the stable default one-window path.
- Added `shot-contact-sheet.png` and embedded it in `review.html` so every
  multi-shot render can be inspected one final shot at a time.
- Preserved visually confirmed source windows across voiceover retiming with a
  bounded `playback_rate`, and added final-source frame evidence so reviewed
  content is not silently trimmed before rendering.
- Preserved diagnostic `contact-sheet.png` on artifact-review failures while
  still removing stale success artifacts such as `remix.mp4`.
- Reframed documentation around auditable rough-cut generation, not full editor
  replacement or true viral-reference decomposition.
- Added `visual-review` candidate boards and `--visual-selections` for explicit
  Codex-assisted shot selection with opaque filenames, asset fingerprints, and
  self-contained frame evidence in the final review page.
- Expanded source preflight to detect upper recording chrome and dark lower
  platform bars, not only dense bright subtitle text.
- Removed the default full-frame render masks that created artificial dark
  bands; crop, caption outline, and source-preflight warnings remain active.

## 0.2.0

- Added local Windows Chinese TTS generation for `voiceover.wav`.
- Added burned-in captions through `captions.ass`.
- Added `contact-sheet.png` with one representative frame per segment.
- Added `review.html` for local visual review.
- Hardened review checks for rendered video audio, voiceover duration, caption artifacts, and contact-sheet detail.
- Cleaned stale success artifacts after blocking failures.
- Updated README and SKILL documentation for the v0.2 experience.

## 0.1.0

- Added the first auditable automatic preview-video workflow.
- Added local asset scanning through `manifest.json`.
- Added timeline planning through `recipe.json`.
- Added asset matching evidence through `matches.json`.
- Added SRT subtitle output and silent preview rendering.
- Added schema and semantic checks to block unsafe paths, missing matches, timeline errors, and reference-video leakage.
