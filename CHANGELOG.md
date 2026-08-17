# Changelog

## Unreleased

- `review.html` now opens with a nontechnical verdict panel answering
  `能不能用`, `先看哪里`, and `主要风险`, so warning runs that may be filename-only
  or visually weak are harder to mistake for publishable videos.
- `run` and `quick` now accept local WAV, MP3, and M4A audio through
  `--voiceover`, so a real narration or external TTS can be used when Windows
  SAPI has no Chinese voice; non-WAV input is normalized to the work directory
  and remains fully validated.
- `doctor` now verifies that Windows SAPI can select the detected Chinese voice,
  so it no longer reports readiness when the later TTS step would fail; its
  failure output points to the local `--voiceover` audio fallback.
- Added an optional `edge-tts` narration backend. `auto` prefers a working local
  Windows voice and falls back to Edge TTS when installed; `windows` and `edge`
  can be selected explicitly, while `--voiceover` remains the offline override.
- Online TTS failures now keep the review artifacts and report a compact
  actionable error instead of leaking the provider's full traceback.
- Failed runs now keep a local `review.html` alongside `review.md`; the page
  clearly marks missing media as not generated, links review artifacts, and
  embeds source-preflight diagnostic frames when available.
- Product `quick` material-diagnosis failures now also write that review page
  with `diagnosis.md` and the visual candidate board, and CLI runs print the
  page to open directly.
- The release gate now requires non-empty `review.html`, `remix.mp4`, and
  `contact-sheet.png` evidence for each real pass, validates that the remix is
  decodable with video and audio and that the contact sheet is a real image,
  and verifies that dirty packs do not leave a remix artifact.
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
- Repeated platform UI or original-subtitle warnings across source segments
  now fail during preflight before voiceover and rendering.
- Visual-selection runs now explain that visible choices replace filename role
  matching, instead of reporting opaque filenames as missing material.
- Material diagnosis now warns when different filenames share byte-identical
  media, while documenting that re-encoded or mother-video copies need further
  visual review.
- Product `quick` now performs a conservative visual-diversity audit on
  close-duration, same-sized candidates and reports likely re-encoded or
  cropped copies without claiming certain mother-video identity.
- The visual-diversity audit also checks selected longer/shorter pairs for
  conservative partial-frame overlap, reports coverage, and still avoids
  claiming certain mother-video identity.
- Source preflight no longer escalates one warning repeatedly when the same
  source video is reused across segments; it still escalates repeated samples
  within a segment or the same warning across independent source files.
- Source preflight now uses manifest SHA-256 identities when deciding whether
  repeated warnings come from independent files, so renamed byte-identical
  copies are not counted as separate evidence.
- The no-script `quick` path now uses a complete five-beat home-cleaning
  product script instead of placeholder labels, so the first preview has a
  real hook, pain, feature, demonstration, and closing line.
- Packaged the JSON schemas inside the wheel and added a clean-install check so
  installed `demo` runs do not depend on the repository checkout.
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
- Bound visual selections to the candidate board's role and caption metadata;
  stale selections now fail before rendering, and a missing candidate sheet
  is treated as a blocking evidence error instead of producing a broken link.
- Added `scripts/check_release_gate.py` and an evidence-ledger template that
  keep automated test health separate from real-material, dirty-pack, and
  outside-user release evidence; manifest SHA-256 identities prevent one
  source pack from being counted multiple times.
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
