# Product-Grade Progress

## 2026-08-13

User reset the goal: `jianji-flow` must be genuinely useful before open source and must not be shipped as a vanity repository.

Actions completed:

- created persistent goal for product-grade `jianji-flow`;
- added `docs/product-quality-bar.md`;
- added `docs/validation/product-grade-validation.md`;
- added `docs/commercialization.md`;
- rewrote `task_plan.md` around product-grade phases;
- added `docs/product-grade-findings.md`;
- kept current code changes from the v7 hardening round:
  - stronger visual remix crop and safe-area masks;
  - voiceover-duration retiming;
  - section-heading script cleanup;
  - higher caption placement;
  - same-source and platform UI review warnings.

Latest verification before this reset:

- `python -m pytest -q` -> 237 passed;
- `python scripts/run_smoke.py` -> smoke passed;
- `out/real-material-remix-v7/review.md` -> warning;
- `out/real-material-remix-v7/contact-sheet.png` -> visible rough-cut remix, not publish-ready.

Latest verification after the source-preflight and review-honesty pass:

- `python -m pytest -q` -> 249 passed;
- `python scripts/run_smoke.py` -> smoke passed;
- `python scripts/run_p0.py` -> p0 passed;
- `out/real-material-remix-v13/review.md` -> warning, not pass;
- `out/real-material-remix-v13/contact-sheet.png` -> visible five-segment rough cut, but still only role-labeled assembly;
- source preflight removed `source-diagnostics` after clean source checks, so no severe platform UI frame was retained for v13.

Product judgment:

- v13 is a reviewable rough cut, not a release demo.
- The automated review now warns when every selected segment is backed only by filename evidence.
- This is an intentional honesty gate: filename-only role assembly must not be marketed as visual understanding.
- Source-preflight warnings are carried into the final review, and summary text prioritizes source visual risk over weaker filename-only warnings.
- The next quality gap is story/usefulness: the system must tell users when clips do not yet support a compelling product story.

Current next step:

- add a material-story diagnosis that distinguishes "enough clips to render" from "enough visual evidence to support a usable product short";
- improve first-use review copy so non-technical users understand warning states without reading JSON.

Parallel product audit result:

- public release is not recommended yet;
- MVP should be reframed as role-based material assembly, not true reference video decomposition;
- next priority is pre-render material quality gates and blind first-time-user validation.
