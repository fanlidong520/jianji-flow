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
| Blind-user trial | first-time usability evidence | monetization push |

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
- final `remix.mp4`;
- written manual judgment: pass, warning, or fail with reason.

## Automated Gates To Add

These gates should be implemented before public launch:

- preflight material quality diagnosis for platform UI and old subtitles;
- source-diversity check that detects clips split from the same mother video when possible;
- multi-frame sampling inside each segment, not only one contact-sheet midpoint;
- caption placement check against lower safe-area residue;
- "visual shell" detector comparing source frames and output frames;
- review status escalation when platform UI warnings are severe or repeated;
- story-support review that warns or fails when clips can render but do not provide enough evidence for the script;
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

- `python -m pytest -q` -> 266 passed;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- `out/real-material-remix-v17/diagnosis.md` -> all product roles ready by filename/duration screening only;
- `out/real-material-remix-v17/review.md` -> warning, not pass;
- `out/real-material-remix-v17/remix.mp4` -> 23.233s, 592x1280, 30fps, audio present;
- `review.md` and `review.html` include `Story support` with roles, filename-only roles, visual-evidence roles, and weak-evidence roles;
- `Story support.next_action` should name the weak roles to replace or manually verify;
- warning is correct because all five story roles rely on filename evidence and have no non-filename visual evidence.

## Launch Rule

Do not announce the project publicly until:

- at least three real-material packs reach `pass` or actionable `warning`;
- no known false pass remains;
- installation and quickstart are verified from a clean environment;
- README shows honest examples, including a warning case.
