# jianji-flow Product Quality Bar

This document defines what "good enough to open source" means for `jianji-flow`.
It is intentionally stricter than "the command exits successfully".

## Product Promise

`jianji-flow` should help a creator turn local raw clips and a short script into a reviewable rough-cut video fast.
The output does not need to replace a professional editor, but it must clearly save work:

- selects and orders clips into a short-video structure;
- produces synchronized voiceover and readable captions;
- avoids obvious platform UI, old subtitles, blank frames, and stale artifacts;
- explains exactly why an output is usable, needs review, or should not be used;
- gives the user a clear next action within 30 seconds;
- lets the user repair one weak segment without blindly rebuilding the whole cut.

## Non-Negotiable Standards

An output must not be treated as usable when any of these are true:

- it is visually indistinguishable from the source video except for voiceover;
- it contains obvious old platform UI, comment bars, like/share controls, or old subtitles in the safe area;
- the captions are unreadable, garbled, too low, or out of sync with voiceover;
- the generated video is silent, too short, too long, blank, frozen, or mostly background color;
- selected clips do not match the script intent enough for a human to understand the story;
- the review page hides uncertainty or reports `pass` when visual warnings remain.
- every selected segment is supported only by filename evidence; this can be a reviewable `warning`, but not `pass`.
- most story roles lack non-filename visual evidence; this must be `warning` or `fail`, not `pass`.

## Usability Scorecard

Every real-material validation run should be judged on a 0-3 scale:

| Area | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| Setup | cannot run | runs with debugging | runs from README | first-time user can succeed quickly |
| Material diagnosis | no guidance | vague errors | lists missing/risky material | tells user exactly what clips to add or replace |
| Visual remix | source shell | basic cuts only | visible crop/order/package | clearly feels like a new rough cut |
| Captions and voice | broken | understandable with issues | readable and synced | publish-review quality |
| Review honesty | false pass | warnings unclear | warnings actionable | decision and next action are obvious |
| Open-source polish | unclear | developer-only | usable README | contributor-friendly examples and tests |

Minimum open-source bar:

- no area below 2 on synthetic fixtures;
- no area below 2 on at least three real-material packs;
- at least three independent real-material packs must reach `pass`, not only actionable `warning`;
- at least one pack must use non-semantic filenames and still show meaningful visual shot selection;
- at least five outside users must try the README flow before public launch;
- review honesty must score 3 before public launch.

## Current v7 Judgment

`out/real-material-remix-v7` is a useful proof that the workflow now performs visible remixing.
It is not a publish-ready product demo.

Passes:

- normal `quick` pipeline generated the sample;
- voiceover retiming works;
- captions are valid UTF-8 and visible;
- stronger crop removes most platform UI;
- review warns about remaining old subtitle/platform UI risk.

Still not good enough:

- material came from one already-posted video, so old embedded text remains;
- one warned segment still has lower-safe-area residue;
- source preflight warnings now appear in material diagnosis, but the tool still cannot judge whether clean clips truly support the product story;
- no independent real-material packs have passed the same bar yet.

## Current v23 Judgment

`out/real-material-remix-v23` should be judged as an honesty checkpoint, not a launch demo.
The review layer now exposes `Story support` so a run can distinguish "enough clips to render" from "enough evidence to trust the product story."

Passes:

- full test suite passed with 277 tests;
- smoke and P0 passed;
- product `quick` writes `diagnosis.md` even when material roles can be tried, so filename/duration screening remains visible without calling them visually ready;
- product `quick` labels filename/duration-ready clips as `CANDIDATE`, not user-visible `READY`;
- product `quick` appends source preflight warnings/failures to `diagnosis.md` when risky source frames are found;
- `out/real-material-remix-v23/diagnosis.md` shows all five roles as `CANDIDATE`, not visually ready;
- `out/real-material-remix-v23/matches.json` records a `window` score for every selected segment;
- `out/real-material-remix-v23/matches.json` uses non-zero source windows for 3 of 5 segments after window scoring;
- `out/real-material-remix-v23/matches.json` records `source-preflight:clean` for all five selected segments after clean source-frame sampling;
- `out/real-material-remix-v23/window-diagnostics` keeps sampled candidate frames for audit;
- `out/real-material-remix-v23/remix.mp4` is 37.907s, 592x1280, with audio present;
- source preflight runs before voiceover/render;
- review status must be `warning`, not `pass`, when most story roles have no non-filename visual evidence.
- `Story support` must name the weak roles in `next_action` so a non-technical user knows what to replace or manually verify.
- `fixes.template.json` should convert weak or low-confidence segments into editable repair entries.

Still not good enough:

- every segment is matched by filename evidence only;
- `source-window` evidence is only a clip-window selection signal, not visual understanding;
- `window-score` evidence is only frame-information scoring, not semantic story matching;
- `source-preflight:clean` means sampled source frames did not trigger platform UI / old-subtitle checks; it is not story-matching evidence;
- the contact sheet shows a rough assembly, but not a strong product-story edit;
- the system still does not truly understand product visuals;
- full test runtime increased after frame scoring and needs follow-up optimization;
- this should be treated as a local validation artifact, not a public launch demo.

## Current v24 Judgment

The segment-fix workflow is a usability improvement, not a launch pass.

Passes:

- `fixes.template.json` is generated for weak or low-confidence segments;
- `--fixes` can pin a segment id or role to a replacement asset;
- blank template entries are ignored so a user can fill only one segment;
- filled fixes entries fail clearly when the target, replacement path, source range, or duration is invalid;
- `matches.json` records `override:seg-xxx` or `override:role:xxx` when a fix is applied;
- automated regression verifies that replacing one segment visibly changes the corresponding contact-sheet tile.
- real-material `out/real-material-remix-v24-fixed-seg003` records `override:seg-003` and changes the third contact-sheet tile from the base v24 run.
- review now warns when adjacent segments use the same source after a fix.

Still not good enough:

- fixes make correction easier, but do not prove semantic visual understanding;
- real-material segment replacement can create repeated adjacent visuals; the new adjacent-source warning catches this, but it still requires a better automatic replacement recommender;
- the repair file is still JSON, so a non-technical UI or copyable review action is still needed;
- real-material v24 must be judged as a repair-loop checkpoint, not a public launch demo.

## Current v25 Judgment

The repair template now ranks candidates and labels risky recommendations instead of presenting every candidate as equally safe.

Passes:

- `fixes.template.json` includes `candidate_assets` with score, reasons, and warnings;
- `recommended_asset_path` is the highest-ranked candidate for each weak segment;
- `recommendation_status` is `recommended`, `best_available_with_warnings`, or `no_candidate`;
- candidate ranking prioritizes avoiding adjacent repeated source videos before weaker fallback role matching;
- real-material `out/real-material-remix-v25/fixes.template.json` marks `seg-003` as `best_available_with_warnings` because the only long-enough candidate would repeat adjacent `seg-004`;
- `out/real-material-remix-v25-fixed-seg003` still records `override:seg-003`, changes the third contact-sheet tile, and keeps the adjacent-source warning in `review.md`.

Still not good enough:

- the recommender can identify risk, but cannot yet find or create a better semantic replacement when the local asset pool is too small;
- fallback candidate reasons are still structural, not visual-semantic;
- a non-technical review action should make the recommended path copyable without editing JSON manually.

## Current v27 Judgment

The workflow now avoids two product-harmful forms of false confidence: adjacent source repetition during initial matching, and wrong-role repair recommendations.

Passes:

- initial matching prefers a different adjacent source when another same-role asset is available;
- real-material `out/real-material-remix-v26/matches.json` uses five different source videos for five product segments and records `sequence-diversity:avoids-adjacent-source` after the first segment;
- repair candidates now include `role_match`;
- wrong-role fallback candidates receive `role mismatch; filename-only fallback` warnings;
- when no duration-ready same-role replacement exists, `recommended_asset_path` is blank and `recommendation_status` is `no_candidate`;
- real-material `out/real-material-remix-v27/fixes.template.json` no longer recommends feature/evidence/cta clips as clean replacements for hook, pain, feature, evidence, or cta weak roles when the only alternatives are wrong-role assets;
- if multiple weak segments would use the same replacement, the later recommendation is downgraded with `already recommended for another segment`.

Still not good enough:

- this is still role/file-name logic, not semantic visual matching;
- the current real-material pack has only one same-role clip per story role, so repair often reports `no_candidate`;
- fallback candidates remain useful only for human inspection;
- the next product step should generate and inspect multiple visual windows per source asset so a single clip can provide several meaningful replacement candidates.

## Current v29 Judgment

The review output now explains the cut segment by segment instead of forcing the user to cross-check JSON files.

Passes:

- `review.md` and `review.html` include a `Storyboard` section;
- each storyboard row shows segment id, role, caption, selected asset, source range, evidence, and risk;
- real-material `out/real-material-remix-v29/review.md` shows five storyboard rows for hook, pain, feature, evidence, and cta;
- storyboard risks correctly remain `filename-only match` on real material, so the page explains why the rough cut still needs manual review;
- retimed `source-window` evidence now matches the retimed `source_start_ms` and `source_end_ms`, preventing conflicting clip-window claims in the review page.

Still not good enough:

- the storyboard explains the existing choice, but it does not yet show visual candidate thumbnails or let the user choose an alternative without JSON;
- the page still reports evidence strings such as `filename-role` and `window-score`; these need friendlier labels before a non-technical user trial;
- the next product step should add per-segment candidate frames and a plain-language "why this shot" explanation.

## Current v30 Judgment

The repair loop now has a safer non-JSON path for applying one clean recommendation.

Passes:

- `--apply-recommendation SEGMENT_ID` applies a clean `recommended_asset_path` from `fixes.template.json`;
- warned recommendations and `no_candidate` entries fail clearly instead of being auto-applied;
- `matches.json` records `override:seg-xxx` after an applied recommendation;
- real-material `out/real-material-apply-rec-v30-fixed/matches.json` records `override:seg-003` after applying `seg-003` from the generated template;
- regression tests cover clean application and warning rejection.

Still not good enough:

- applying a recommendation does not prove the shot is visually different or better;
- the v30 real-material validation intentionally duplicated a feature clip to create a clean recommendation, and the contact-sheet tile difference was 0.0 because the alternate file had identical frames;
- the next product step must detect visually duplicate candidates and prefer or report genuinely different frames.

## Current v31 Judgment

The repair recommender now catches one concrete false-improvement failure: a different file path with the same picture.
This improves trust, but it is still not real visual editing.

Passes:

- same-role repair candidates are checked with sampled frames before being called clean;
- the checker samples the current selected source window instead of only the beginning of the file;
- duplicate-looking candidates are downgraded to `best_available_with_warnings`;
- failed visual checks downgrade the candidate instead of failing the whole run;
- wrong-role fallback candidates are not visually checked or promoted as clean recommendations;
- `review.md` exposes `visual_similarity_diagnostics` when diagnostic frames are written;
- CLI wording for warning output is now `review required`, not `completed`;
- `--apply-recommendation` refuses visually similar or visually unchecked recommendations.

Still not good enough:

- this only prevents one kind of false improvement; it does not select semantically better shots;
- the output can still look unchanged when the local material lacks genuine alternatives;
- the review page still needs side-by-side candidate frames and plain-language reasons;
- public launch still requires real product-material packs, non-semantic filename validation, and blind-user trials.

Strict current product judgment:

Do not present `jianji-flow` as a finished automatic editor yet.
The honest current claim is a local, auditable rough-cut workflow whose repair recommendations are becoming safer.
The next product milestone is true visual shot selection: given unhelpful filenames, the system must still choose clips that support hook, pain, feature, evidence, and CTA better than a simple file-order baseline.

## Current v32 Judgment

The review layer now shows repair candidates visually instead of hiding them in JSON.
This improves usability and trust, but it still does not prove the automatic cut is good.

Passes:

- `candidate-review.html` is generated on successful or warning runs;
- `candidate-frames/` contains current-segment and candidate thumbnails used by that page;
- `review.md` and `review.html` link to the candidate review output;
- candidate panels show recommendation status, reasons, warnings, role-match risk, and frame extraction failures;
- failed artifact-review runs remove stale candidate-review artifacts so a failed run does not look repair-ready.

Still not good enough:

- the candidate page makes choices inspectable, but it does not choose better semantic shots by itself;
- wrong-role fallback candidates can still appear for manual inspection when the local asset pool lacks same-role alternatives;
- the output may still be a role-labeled rough cut rather than a visibly improved product edit;
- the next product milestone remains true visual shot selection and before/after change reporting.

## Current v33 Judgment

The repair loop can now expose alternate time windows inside the same source file.
This is closer to real editing because one long clip can yield more than one possible shot.
It is still not a clean automatic improvement.

Passes:

- repair candidates can include `source_start_ms` and `source_end_ms`;
- clean recommendation application carries `recommended_source_start_ms` into the generated fixes file;
- `candidate-review.html` samples candidate frames from the candidate window, not only from the current segment's start;
- candidate-review recommendation labels match both asset path and `source_start_ms`, so same-path windows are not all shown as recommended;
- `candidate_asset_paths` uses `path#source_start_ms` for windowed candidates, while `candidate_assets` remains the authoritative review data;
- same-source alternate windows are marked with `same source window; manual review required`;
- real-material `out/real-material-same-source-windows-v33` exposes same-source candidates for evidence and CTA instead of only wrong-role fallbacks.

Still not good enough:

- same-source windows can still feel repetitive, so they must not be auto-applied as clean recommendations;
- window candidates still make the JSON more complex than a simple file replacement;
- hook, pain, and feature still lacked clean same-role alternatives in the current real-material pack;
- before/after change reporting is still needed so users can see exactly what a repair changed.

## Current v34 Judgment

Fix runs now produce a `Change report`.
This directly addresses the usability complaint that a user could not tell what the tool actually changed.

Passes:

- `review.md` and `review.html` can show changed segments with before/after asset paths, before/after source ranges, before/after sampled frames, picture-change score, sampling note, and override reason;
- `build_change_report` separates changed and unchanged segments from before/after `matches.json`;
- `build_change_report` lists unaccounted segments instead of silently skipping mismatched before/after matches;
- fix runs write `change-diagnostics/` frame samples used to score picture change;
- `--apply-recommendation` integration test verifies that a recommended source-window fix produces a visible change report in both review formats.
- real-material `out/real-material-change-report-v34/review.html` shows before/after frames for `seg-004` and keeps the run at `warning`.

Still not good enough:

- the change report proves what changed, not whether the new shot is semantically better;
- the sampled picture-change score is a rough frame comparison, not a story-quality score;
- public launch still needs non-semantic filename real-material packs and blind-user validation.

## Current v35 Judgment

The workflow now has an explicit visual-selection loop for opaque filenames. It is a meaningful trust improvement because the reviewer can inspect candidate frames and the final report preserves the exact selection evidence. It is still not autonomous semantic editing and is not a public launch pass.

Passes:

- `visual-review` generates a bounded candidate board with three sampled frames per candidate without using filename roles;
- `--visual-selections` validates candidate identity, segment binding, asset fingerprint, source range, and frame fingerprints before rendering;
- `review.md` and `review.html` copy the selected candidate sheet and frames into `visual-selection-evidence/`, so the final review is self-contained;
- a real home-product pack with opaque names `IMG_001.mp4` through `IMG_005.mp4` completed the visual-selection workflow and produced a visibly rearranged five-segment cut;
- the same real run honestly remained `warning` because the feature role had no genuinely clear candidate;
- mutating a selected candidate frame caused a pre-render failure and produced no `remix.mp4` or `voiceover.wav`;
- the malformed-material pack was blocked before manifest creation and produced no `remix.mp4`.
- source preflight now catches the real pack's top recording chrome and bottom platform bar, preserving diagnostic frames and a publish-blocking warning.

Still not good enough:

- candidate generation is deterministic window sampling; it does not understand product semantics by itself;
- Codex or human visual review is still required to choose candidates and write reasons;
- the current real source contains old in-video text/platform residue, so it is not a clean publishing pack;
- no three-pack real-material pass matrix or outside-user trial has been completed;
- the product still needs a stronger automatic semantic selector or a deliberately simple review UI before it can claim easy one-click editing.

Strict current product judgment:

Do not present `jianji-flow` as a finished automatic editor. The honest current claim is a local, auditable rough-cut workflow with an explicit Codex-assisted visual shot-selection loop. The next gate is to validate independent clean material packs and compare this workflow against a blind file-order baseline before public release.

## Current v36 Judgment

The renderer no longer creates full-frame dark bands to cover source risk. This is a visible quality improvement: the real opaque-filename output keeps its crop and readable outlined captions without looking like a masked template. Source residue remains a warning and is not silently hidden.

Passes:

- the vertical render filter no longer contains default `drawbox` masks;
- the real `run-v35f` contact sheet and extracted frame show no artificial top or bottom bands;
- source-preflight still reports the real pack's platform chrome and original overlay text;
- `354` tests, smoke, and P0 pass after the renderer change.

Still not good enough:

- the user-provided source material still contains original yellow text and is not a clean publishing pack;
- the workflow still needs Codex-assisted visual selection for opaque filenames;
- three independent clean packs and outside-user trials remain outstanding.

## Current v37 Judgment

The review output now makes the visible edit easy to verify against the reference instead of asking the user to infer it from filenames or a voiceover. This is a verification improvement, not a claim of semantic editing.

Passes:

- every rendered run writes `reference-comparison.png` with the same number of relative storyboard samples from the reference and remix;
- `review.html` embeds the comparison next to the playable remix and contact sheet;
- artifact review verifies the comparison image when the pipeline creates it;
- Codex visual-selection instructions now require the agent to inspect frames and write the selection JSON, so the user does not carry the intermediate JSON workflow.
- source preflight now evaluates the same cropped safe area that the renderer exposes, so platform chrome outside the visible frame is not reported as a false publishing risk.

Still not good enough:

- the comparison proves visible difference, not that the selected shot supports the spoken claim;
- the real home-product pack still contains platform residue and lacks a strong feature shot;
- the editor still assembles one source window per story segment, so pacing and multi-shot montage remain limited;
- three clean real-material packs and outside-user trials are still required before public launch.

## Current v38 Judgment

The optional multi-shot path now turns a selected source window into several
short source ranges at detected scene boundaries. The renderer flattens those
ranges into the parent story segment, and the final `shot-plan.json` is
resynchronized after voiceover retiming so the audit file matches the output
timeline.

Passes:

- scene detection is bounded by minimum shot duration and maximum shot count;
- unsafe or failed detection falls back to the original window with a visible warning;
- shot paths are checked against the manifest, asset root, reference hash, and
  exact parent segment duration;
- `review.md` and `review.html` expose final boundaries and shot counts;
- `shot-contact-sheet.png` exposes one labeled frame for every final rendered shot;
- visually confirmed source windows keep their reviewed content across voiceover
  retiming through a bounded recorded playback rate;
- low-confidence matches are excluded from automatic multi-shot splitting and
  remain visible in the shot plan as `skipped_low_confidence` until visual
  review confirms them;
- adjacent segments with an identical source shot sequence are flagged in the
  shot plan so repeated footage is reviewed before publishing;
- the stable default path remains unchanged unless `--multi-shot` is requested.

Still not good enough:

- scene boundaries are structural evidence, not semantic understanding of the
  spoken claim or reference pacing;
- the real home-product pack still needs clean source material and stronger
  feature evidence;
- the multi-shot path needs three clean real-material packs and outside-user
  trials before it can become the default or be called publish-ready.

## Product Principle

Do not optimize for impressive automation claims.
Optimize for a creator trusting the review result.
