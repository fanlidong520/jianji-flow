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
- Added a storyboard section to `review.md` and `review.html` so each segment's
  role, caption, source range, evidence, and risk can be checked without opening
  JSON files.
- Kept retimed `source-window` evidence synchronized with retimed source ranges
  so review pages do not show conflicting clip windows.
- Preserved diagnostic `contact-sheet.png` on artifact-review failures while
  still removing stale success artifacts such as `remix.mp4`.
- Reframed documentation around auditable rough-cut generation, not full editor
  replacement or true viral-reference decomposition.

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
