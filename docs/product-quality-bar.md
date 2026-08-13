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
- gives the user a clear next action within 30 seconds.

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

Still not good enough:

- every segment is matched by filename evidence only;
- `source-window` evidence is only a clip-window selection signal, not visual understanding;
- `window-score` evidence is only frame-information scoring, not semantic story matching;
- `source-preflight:clean` means sampled source frames did not trigger platform UI / old-subtitle checks; it is not story-matching evidence;
- the contact sheet shows a rough assembly, but not a strong product-story edit;
- the system still does not truly understand product visuals;
- full test runtime increased after frame scoring and needs follow-up optimization;
- this should be treated as a local validation artifact, not a public launch demo.

## Product Principle

Do not optimize for impressive automation claims.
Optimize for a creator trusting the review result.
