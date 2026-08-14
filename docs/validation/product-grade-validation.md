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

## Launch Rule

Do not announce the project publicly until:

- at least three real-material packs reach `pass`;
- at least one real-material pack uses non-semantic filenames and still reaches `pass`;
- at least one dirty-material pack is correctly blocked as `fail`;
- at least five outside users try the README quickstart, with four finishing in 10 minutes and four judging the output as visibly re-edited;
- no known false pass remains;
- installation and quickstart are verified from a clean environment;
- README shows honest examples, including a warning case.
