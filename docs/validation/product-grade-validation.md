# Product-Grade Validation Plan

This is the validation plan for making `jianji-flow` good enough to open source.

## Validation Levels

| Level | Purpose | Required Before |
| --- | --- | --- |
| Unit tests | lock small behavior | every code change |
| Smoke | prove main paths run | every local checkpoint |
| P0 | prove critical safety paths | every commit/PR |
| Synthetic fixture review | stable regression evidence | every release candidate |
| Real-material review | product usefulness evidence | open-source launch |
| Blind-user trial | first-time usability evidence | open-source launch |

## Required Real-Material Packs

Before public launch, maintain at least these packs under a non-committed local validation folder:

- home cleaning product clips: clean raw clips without platform UI;
- home storage or kitchen product clips: multiple independent shots;
- talking-head clip pack: one long talk plus B-roll or cutaway material.

Each pack needs:

- source folder;
- clean script;
- generated `review.md`;
- generated `review.html`;
- `contact-sheet.png`;
- `candidate-review.html` when fixes are generated;
- candidate-frame screenshots when fixes are generated;
- final `remix.mp4`;
- written manual judgment: pass, warning, or fail with reason.

## Automated Gates To Add

These gates should be implemented before public launch:

- preflight material quality diagnosis for platform UI and old subtitles;
- source-diversity check that detects clips split from the same mother video when possible;
- multi-frame sampling inside each segment, not only one contact-sheet midpoint;
- visual-similarity checks for same-role repair candidates, with duplicate-looking or unchecked recommendations blocked from one-command application;
- caption placement check against lower safe-area residue;
- "visual shell" detector comparing source frames and output frames;
- review status escalation when platform UI warnings are severe or repeated;
- story-support review that warns or fails when clips can render but do not provide enough evidence for the script;
- repair-loop report that turns weak or low-confidence review findings into an editable fix file;
- README quickstart test on a clean checkout.

## Manual Review Checklist

For every real-material run:

- Can a viewer understand the product in 3 seconds?
- Does every clip support the current voiceover line?
- Does `Story support` explain whether the rough cut is role-labeled only or backed by stronger evidence?
- Does the video look newly edited rather than revoiced?
- Are old captions, platform UI, comments, or creator handles visible?
- Are captions readable on a phone screen?
- Does `review.md` match what the human sees?
- If a candidate review exists, can the human see what would change before applying a fix?
- Is the next action clear enough for a non-technical creator?

## Current Evidence

Latest local checkpoint:

- `python -m pytest -q` -> 237 passed;
- `python scripts/run_smoke.py` -> smoke passed;
- `out/real-material-remix-v7/review.md` -> warning, not pass;
- `out/real-material-remix-v7/contact-sheet.png` -> visible remix, but old lower-safe-area residue remains in one segment.

Latest local checkpoint after source-preflight hardening:

- `python -m pytest -q` -> 249 passed;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- `out/real-material-remix-v13/review.md` -> warning, not pass;
- `out/real-material-remix-v13/remix.mp4` -> 23.233s, 592x1280, 30fps, audio present;
- `out/real-material-remix-v13/contact-sheet.png` -> five visible segments;
- source preflight found no severe lower-safe-area source residue for v13;
- review warning is correct because all five selected segments are filename-only matches.

Manual judgment for v13:

- Can be used to inspect whether the pipeline assembled a rough cut.
- Should not be used as the public open-source hero example.
- Should not be labeled `pass` until visual/story evidence is stronger than filename-only role labels.

Latest local checkpoint after material diagnosis visibility:

- `python -m pytest -q` -> 277 passed;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- `out/real-material-remix-v23/diagnosis.md` -> all product roles show `CANDIDATE`, not visually ready;
- `out/real-material-remix-v23/matches.json` -> every selected segment has a `window` score;
- `out/real-material-remix-v23/matches.json` -> 3 of 5 selected segments use non-zero source windows after scoring;
- `out/real-material-remix-v23/matches.json` -> all five selected segments include `source-preflight:clean`;
- `out/real-material-remix-v23/window-diagnostics` -> candidate midpoint frames preserved for audit;
- `out/real-material-remix-v23/review.md` -> warning, not pass;
- `out/real-material-remix-v23/remix.mp4` -> 37.907s, 592x1280, audio present;
- `review.md` and `review.html` include `Story support` with roles, filename-only roles, visual-evidence roles, and weak-evidence roles;
- `Story support.next_action` should name the weak roles to replace or manually verify;
- warning is correct because all five story roles rely on filename evidence and have no non-filename visual evidence.
- `source-window` evidence must not be treated as visual evidence.
- `window-score` evidence must not be treated as story-match evidence.
- `source-preflight:clean` evidence must not be treated as story-match evidence.

Latest local checkpoint after segment-fix workflow:

- `fixes.template.json` is generated on successful or warning runs;
- `--fixes` supports segment-id and role-based replacement;
- blank template entries are ignored;
- unknown targets, unknown paths, invalid source ranges, and too-short replacements fail clearly;
- `matches.json` records override evidence when a fix is applied;
- targeted regression proves the replaced contact-sheet segment visibly changes;
- `out/real-material-remix-v24-fixed-seg003/matches.json` records `override:seg-003`;
- v24 fixed third contact-sheet tile differs from base v24 by mean pixel difference about 51.9;
- v24 fixed remains `warning`, because the replacement creates repeated adjacent visuals and source-preflight warnings remain;
- v24 fixed `review.md` now warns that adjacent segments `seg-003` and `seg-004` use the same source video;
- this is a repair-loop improvement, not proof of visual semantic matching.

Latest local checkpoint after candidate-ranking repair template:

- `fixes.template.json` now includes `recommended_asset_path`, `recommendation_status`, `recommendation_warnings`, and scored `candidate_assets`;
- candidate ranking prioritizes avoiding adjacent repeated sources before fallback role matching;
- real-material `out/real-material-remix-v25/fixes.template.json` marks `seg-003` as `best_available_with_warnings`, not a clean recommendation;
- `out/real-material-remix-v25-fixed-seg003/matches.json` records `override:seg-003`;
- v25 fixed third contact-sheet tile differs from base v25 by mean pixel difference about 51.9;
- v25 fixed `review.md` remains `warning` and preserves the adjacent-source warning for `seg-003` and `seg-004`;
- this improves recommendation honesty, but still does not solve semantic visual matching.

Latest local checkpoint after adjacent-source and wrong-role recommendation fixes:

- initial matching now prefers non-adjacent source reuse when another same-role asset is available;
- `out/real-material-remix-v26/matches.json` uses five different source videos for the five product roles and has no adjacent repeated source;
- repair candidates now expose `role_match`;
- wrong-role fallback candidates are kept as manual-inspection candidates but are not promoted to `recommended_asset_path`;
- `out/real-material-remix-v27/fixes.template.json` reports `recommendation_status: no_candidate` for weak roles when no duration-ready same-role replacement exists;
- repeated use of the same recommended replacement across weak segments is downgraded with an explicit warning;
- CLI integration now validates the generated `fixes.template.json` against `fixes.schema.json`;
- `out/real-material-remix-v27/review.md` remains `warning`, correctly stating that all five roles still lack non-filename visual evidence.

Latest local checkpoint after storyboard review output:

- `python -m pytest -q` -> 306 passed;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- `review.md` and `review.html` now include a per-segment `Storyboard`;
- `out/real-material-remix-v29/review.md` has five storyboard rows with role, caption, selected asset, source range, evidence, and risk;
- `out/real-material-remix-v29/review.html` has five `.storyboard-row` entries;
- storyboard risk remains `filename-only match` for all five real-material roles, which is correct because no visual semantic evidence exists yet;
- retimed `source-window` evidence now matches the retimed source ranges in `matches.json` and the storyboard.

Latest local checkpoint after one-command recommendation application:

- `--apply-recommendation SEGMENT_ID` applies one clean recommendation from `fixes.template.json` without editing JSON;
- warned recommendations fail clearly and do not render stale success artifacts;
- `python -m pytest tests/test_fixes.py tests/test_cli.py::test_run_applies_clean_recommendation_from_fixes_template tests/test_cli.py::test_run_rejects_warning_recommendation_without_traceback tests/test_cli.py::test_run_applies_fixes_file_to_one_segment tests/test_cli.py::test_run_reports_invalid_fixes_file_without_traceback -q` -> 14 passed;
- `python scripts/run_p0.py` -> p0 passed;
- `out/real-material-apply-rec-v30-base/fixes.template.json` gives `seg-003` a clean recommendation after adding an alternate same-role feature clip;
- `out/real-material-apply-rec-v30-fixed/matches.json` records `override:seg-003` from `--apply-recommendation seg-003`;
- the v30 contact-sheet third tile mean difference is 0.0 because the alternate file was a duplicate copy, proving the next gate must detect visually duplicate candidates.

Latest local checkpoint after visual duplicate recommendation checks:

- same-role repair candidates are compared against the current selected source window with three sampled frames;
- visually similar candidates are downgraded to `best_available_with_warnings`;
- visual-check failures are also downgraded instead of failing the whole run;
- wrong-role fallback candidates skip visual comparison and remain manual-inspection candidates only;
- `review.md` lists `visual_similarity_diagnostics` when sampled diagnostic frames are written;
- warning CLI output now says `jianji-flow review required`, not `completed`;
- real-material duplicate-feature validation downgraded `seg-003` because the copied candidate looked like the current segment;
- `--apply-recommendation seg-003` rejected the warned recommendation and did not render stale success artifacts.

Strict product audit after v31:

- current outputs are still not launch-quality automatic editing;
- recent improvements make the review and repair loop more honest, but v29 and v31 video outputs can remain visually unchanged;
- public launch requires actual visual shot selection, not only safer reports around filename-based assembly;
- first-run validation must include one real product-material pack with non-semantic filenames such as `IMG_001.mp4`;
- a blind baseline comparison must show that `jianji-flow` beats simple file-order concatenation with voiceover and captions.

Latest local checkpoint after candidate visual review:

- `candidate-review.html` is generated from `fixes.template.json` on successful or warning runs;
- `candidate-frames/` is regenerated on rerun so stale candidate screenshots are removed;
- main `review.md` and `review.html` expose the candidate review path;
- failed artifact-review runs remove candidate-review outputs while preserving diagnostic contact-sheet evidence;
- real-material `out/real-material-candidate-review-v32/candidate-review.html` shows current and candidate frames for all five weak home-product roles;
- real-material v32 correctly remains `warning`: all five roles are filename-only story support and the candidate page exposes wrong-role fallbacks instead of inventing clean replacements;
- this makes repair candidates easier to judge, but it is not yet semantic visual shot selection.

Latest local checkpoint after same-source window candidates:

- `fixes.template.json` can include `recommended_source_start_ms` and candidate-level `source_start_ms` / `source_end_ms`;
- `--apply-recommendation SEGMENT_ID` carries a clean recommended source window into the generated fixes file;
- `candidate-review.html` extracts candidate frames from candidate windows when those fields are present;
- same-source windows are downgraded with `same source window; manual review required`;
- candidate-review labels recommended windows by asset path plus `source_start_ms`, preventing same-path non-recommended windows from being mislabeled;
- `candidate_asset_paths` now uses `path#source_start_ms` for window candidates; reviewers should rely on `candidate_assets` for exact windows;
- targeted regression verifies that a recommended source window changes `matches.json` `source_start_ms`;
- real-material `out/real-material-same-source-windows-v33/fixes.template.json` exposes same-source window candidates for evidence and cta while keeping the run at `warning`;
- this is a stronger repair-inspection loop, but still not a public launch pass.

Latest local checkpoint after fix-run change reports:

- `review.md` and `review.html` include a `Change report` section when a fix file or clean recommendation is applied;
- changed segments show before asset/range, after asset/range, before/after sampled frames, picture-change score, sampling note, and override reason;
- unchanged segments are listed so users can see the fix did not rebuild the whole cut;
- unaccounted segments are listed instead of being silently skipped;
- `change-diagnostics/` stores the sampled frames used for the picture-change score;
- targeted regression verifies that `--apply-recommendation seg-003` writes the change report and diagnostics;
- real-material `out/real-material-change-report-v34/review.html` embeds before/after sampled frames for `seg-004`, with `Picture change` 51.9 and `review required` status;
- this improves first-time usability, but it still does not prove semantic visual shot selection.

Latest local checkpoint after visual candidate selection v35:

- `python -m pytest -q` -> 355 passed in 628.96s;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- `visual-review` generated a 45-candidate board for the real home-product material using opaque filenames;
- `out/visual-selection-v35/run-v35e/review.md` and `review.html` record four explicit visual selections and one honest feature-role abstention;
- `out/visual-selection-v35/run-v35e/contact-sheet.png` shows five actual source-window choices, with `seg-002` and `seg-004` changed from the baseline and a `warning` status retained;
- `out/visual-selection-v35/run-v35e/matches.json` now keeps each selected visual candidate's asset and source window aligned with its `candidates` record, including after voiceover retiming;
- `out/visual-selection-v35/run-v35e/source-diagnostics/` contains 15 sampled frames because the new upper/lower platform-chrome checks correctly detected residue in the real pack;
- after deliberately mutating `seg-001-candidate-03-01.png`, the rerun failed before rendering with `visual selection frame fingerprint changed`, and `out/stale-visual-selection-v35/run/review.md` contains no `remix.mp4` or `voiceover.wav`;
- `out/dirty-pack-v35` was blocked on the malformed asset before manifest creation and produced no `remix.mp4`;
- an opaque-filename run without visual selections stopped with a diagnosis instead of pretending filename-based assembly was sufficient.

Product judgment:

- this is a stronger and more honest visual review workflow, not proof of autonomous semantic editing;
- the real pack is still `warning` because the feature shot is not clearly supported and the source material contains old in-video residue;
- public launch remains blocked until three independent real-material packs, a clean non-semantic filename pass, a dirty-pack fail, clean-install verification, and outside-user trials all pass the launch rule.

Latest local checkpoint after render cleanliness v36:

- `python -m pytest -q` -> 355 passed in 628.96s;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- `out/visual-selection-v35/run-v35f/contact-sheet.png` and an extracted frame from `remix.mp4` show the artificial gray/black top and bottom bands are gone;
- captions remain visible through the ASS outline/shadow treatment;
- source preflight still keeps the same run at `warning` and preserves platform-residue diagnostics, so the render cleanup did not weaken the honesty gate.

Latest local checkpoint after reference comparison and crop-aware preflight v37:

- `python -m pytest -q` -> 355 passed in 628.96s;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- Skill validation -> `Skill is valid!`;
- `out/visual-selection-v37/run-v37c/reference-comparison.png` shows five relative storyboard samples from the reference above the remix below, with visibly different source shots;
- the same real run remains `warning` because the feature role is weak and selected source frames still need review;
- source preflight now stores cropped safe-area diagnostics, reducing irrelevant warnings from platform chrome that the renderer removes.

Latest local checkpoint after opt-in multi-shot v38:

- `python -m pytest -q` -> 380 passed in 361.65s;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- Skill validation -> `Skill is valid!`;
- multi-shot unit, schema, semantic, matcher, renderer, and review tests pass;
- final `shot-plan.json` is regenerated after voiceover retiming and matches the
  final `matches.json` shot ranges;
- `shot-contact-sheet.png` makes every final rendered shot inspectable without
  scrubbing the video manually;
- visual-review matches preserve the confirmed source window and record the
  playback rate used to fit the final narration duration;
- the default one-window path remains covered separately, while multi-shot is
  explicitly opt-in during real-material validation;
- no public launch claim is made until clean packs and outside-user trials pass
  the launch rule below.

Latest local checkpoint after conservative multi-shot and duplicate-sequence
audit v41:

- `python -m pytest -q` -> 384 passed in 1108.41s;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- Skill validation -> `Skill is valid!`;
- the real home-product run has all five story roles visually supported after
  reviewing the feature candidate, but remains `warning` because source frames
  contain original platform/subtitle residue and adjacent segments repeat the
  same shot sequence;
- low-confidence segments are kept as one source window instead of being
  automatically split into more questionable shots;
- the current real run is not evidence for public launch; it is a quality gate
  showing exactly what still needs better source material.

Latest package consistency and repeat-validation checkpoint:

- the package now reports `jianji-flow 0.3.0.dev0` from both the source tree
  and a fresh non-editable installation;
- one long-suite run recorded a transient `ffprobe` timeout after 383 passing
  tests; the affected test passed in five isolated reruns, and the next full
  suite passed 384/384 in 344.27 seconds;
- smoke, P0, and skill validation passed again after the version change;
- this does not relax the product launch rule: real-material quality and
  outside-user trials are still outstanding.

Latest source-preflight escalation checkpoint:

- the previous real home-product visual-selection run would have produced a
  37.9-second remix with a `warning`;
- after repeated-warning escalation, the same material now stops before
  voiceover and rendering with `Status: fail` because `seg-001`, `seg-003`,
  and `seg-005` contain source UI/subtitle warnings;
- `out/visual-selection-v44/run-repeat-gate/` retains `review.md`,
  `diagnosis.md`, `source-diagnostics/`, and no `remix.mp4` or `voiceover.wav`;
- when visual selections are present, `diagnosis.md` now says `VISUAL REVIEW
  SUPPLIED` instead of mislabeling opaque filenames as `MISSING`.

Latest conservative source-diversity checkpoint:

- exact duplicate media is grouped by the scanned SHA-256, independent of the
  filename used for each copy;
- a duplicate-material run reported two duplicate groups in `diagnosis.md`
  instead of treating five role-labeled names as five independent clips;
- a real re-encoded fixture pair was scored `0.18` and reported as `SIMILAR
  MEDIA` with sampled diagnostics;
- a real middle segment cut from a longer source was detected as
  `partial-overlap` with score `3.154` and coverage `0.667`;
- this gate intentionally does not claim to detect every re-encoded file or
  clip cut from the same mother video; that remains an open validation item.

Latest full validation after visual-diversity audit:

- `python -m pytest -q` -> 394 passed in 349.81s;
- smoke, P0, and Skill validation passed;
- fresh non-editable installation reports `0.3.0.dev0`, and the installed
  package detects a re-encoded fixture pair as `SIMILAR MEDIA` with score
  `0.18`;
- real home-product visual-selection run v45 still fails before voiceover and
  rendering on repeated source UI/subtitle warnings, with no remix or
  voiceover output.

Latest local A/B checkpoint after feature candidate review v42:

- the feature role remains visually supported and `Story support` is `pass`;
- candidate 04 removes the identical adjacent feature/evidence shot sequence
  found in candidate 05 while keeping a 20-shot plan and a 37.9-second
  video-plus-voiceover output;
- the run remains `warning` because the source pack contains original
  platform/subtitle residue and adjacent segments still draw from the same
  source video;
- this is the strongest result from the current pack, not a clean-pack or
  public-launch result.

Latest clean-install checkpoint:

- created a fresh Python 3.11 virtual environment outside the repository;
- installed the built project with `pip install "E:\\AI-Companion\\jianji-flow[dev]"`;
- `python -m jianji_flow --version` returned `jianji-flow 0.3.0.dev0`;
- `python -m jianji_flow doctor` returned `Ready to run quick draft`;
- `python -m jianji_flow demo --target-width 320 --target-height 180
  --target-fps 12` exited successfully and wrote `remix.mp4`, `review.md`,
  `review.html`, and the contact sheets;
- this check caught and fixed a missing packaged-schema failure before the
  project is presented as installable.

Latest preflight false-positive recalibration and default-script checkpoint:

- source preflight no longer escalates the same warning repeatedly when one
  source video is reused across multiple timeline segments;
- manifest SHA-256 identities are reused by source preflight, so renamed
  byte-identical copies do not become false independent-warning evidence;
- the escalation rule still fails repeated sampled warnings within one source
  segment or the same warning family across independent source files;
- the regression suite now passes `399/399`, with smoke and P0 passing again;
- the no-script quick path now produces a five-beat cleaning product script
  instead of placeholder labels: hook, pain, feature, demonstration, and
  closing line;
- real-material run `out/visual-selection-v50/run-default-script/` renders a
  20-shot preview with the default script and remains `warning` because the
  source pack still contains original overlay/UI risk and adjacent source
  reuse;
- visual inspection of the real contact sheet confirms that the preview is
  visibly re-edited, but the source pack is still not publish-ready.

Latest partial-mother-clip audit checkpoint:

- the source-diversity audit now compares a longer/shorter pair across
  uniformly extracted frames instead of assuming matching timestamps;
- a real 4.5-second middle cut from `IMG_003.mp4` was reported as
  `partial-overlap`, score `3.154`, coverage `0.667`;
- the audit remains a warning-only signal and does not prove all clips from
  the same mother video are detected;
- the full suite remains green at `399/399` after the new audit and output
  formatting.

Latest visual-selection integrity checkpoint:

- a stale real selection file from the previous script was rejected before
  rendering with `visual selection caption changed`;
- generated candidate manifests now carry role and caption metadata, so
  deleting those fields from the selection JSON cannot bypass stale-board
  detection;
- a missing `visual-candidate-sheet.png` is a blocking input error, and final
  reports reference the copied evidence inside the current work directory;
- a fresh real-material selection was correctly blocked by repeated old-title
  and platform-residue warnings across independent source files, so no dirty
  remix was emitted.

Latest regression checkpoint after visual-selection integrity hardening:

- `python -m pytest -q` -> `403 passed in 376.18s`;
- smoke, P0, Skill validation, and `jianji-flow doctor` passed;
- the clean synthetic workflows still emit `review required` for review-only
  output instead of claiming a publish-ready result.

Latest release-gate automation checkpoint:

- `scripts/check_release_gate.py` now verifies review status, manifest
  SHA-256 material identity, independent-pack count, dirty-pack failure,
  README honesty, and outside-user evidence;
- the same manifest identity or review path cannot be counted as multiple
  independent packs;
- the example ledger correctly returns `blocked` and writes both machine and
  human reports when evidence is absent;
- `python -m pytest -q` -> `411 passed in 368.70s`;
- smoke, P0, Skill validation, and `jianji-flow doctor` passed again.

## Launch Rule

Do not announce the project publicly until:

- at least three real-material packs reach `pass`;
- at least one real-material pack uses non-semantic filenames and still reaches `pass`;
- at least one dirty-material pack is correctly blocked as `fail`;
- at least five outside users try the README quickstart, with four finishing in 10 minutes and four judging the output as visibly re-edited;
- no known false pass remains;
- installation and quickstart are verified from a clean environment;
- README shows honest examples, including a warning case.
