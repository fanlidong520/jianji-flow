# Changelog

## Unreleased

- Planned v0.3 usability layer: `doctor`, `demo`, `quick`, material diagnosis,
  and plain-language review summary.

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
