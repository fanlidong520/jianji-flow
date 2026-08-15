# Launch And Business Path

This project should earn trust before it tries to earn revenue. The current
repository is a local, auditable rough-cut skill. It is not yet a publish-ready
editor and it should not be sold as one.

## Release Stages

### 1. Private quality gate

- Keep the current PR draft open.
- Require three independent real-material packs, including one pack with
  opaque filenames, before calling the workflow generally reliable.
- Require a dirty-material pack to stop with a useful failure.
- Require five outside users to try the README path; at least four should
  finish within ten minutes and at least four should say the result is visibly
  re-edited.
- Keep the known limitations visible: semantic matching, mother-video
  detection, source residue, and human product-accuracy review.

### 2. Public free core

Publish the CLI and Codex skill under the existing MIT license only after the
private gate passes. The free core should include:

- local media scanning and material diagnosis;
- visual candidate review and auditable selections;
- voiceover, captions, preview render, and review artifacts;
- honest warning/fail behavior;
- reproducible fixtures and validation scripts.

Do not put a paywall around the basic ability to inspect the output. The open
source project needs real users and real failure reports more than it needs an
early subscription screen.

### 3. First paid offer: done-with-you delivery

The first paid offer should be a narrow service, not a platform:

> Give us one reference video, one product script, and one clean asset folder;
> receive a reviewed rough cut, a source-risk report, and a short list of
> missing shots.

This tests whether the workflow solves a painful job for a real creator. Keep
the service manual where judgment is still required. Record each delivery's
input pack, selected shots, warnings, revision count, time spent, and whether
the customer used the result.

Do not set a permanent price from theory. Start with a small paid pilot, then
raise or reshape the offer only after several people pay and the delivery time
is measurable.

### 4. Paid product layers after repeated payment

Only promote a paid product after the same paid work repeats:

- **Pro workflow:** batch runs, saved recipes, stronger asset preparation,
  provider choices, and priority review reports.
- **Team workflow:** shared projects, reusable product libraries, review roles,
  audit history, and support.
- **Service/support:** onboarding, custom templates, and managed quality review.

These layers are candidates, not commitments. A feature belongs in a paid
layer only when it has appeared in multiple paid deliveries or removes a
measured delivery bottleneck.

## What Not To Build Yet

- No full CapCut/Jianying replacement.
- No cloud rendering platform before local output quality is trusted.
- No payment integration before a person has agreed to pay for the current
  result.
- No generic AI video SaaS positioning.
- No claim that the reference video has been semantically decomposed.

## Evidence Ledger

Every release decision should be tied to evidence, not enthusiasm:

| Decision | Minimum evidence |
| --- | --- |
| Public beta | launch rule in `docs/validation/product-grade-validation.md` passes |
| First paid pilot | one real customer pays for a reviewed delivery |
| Repeatable paid offer | at least three paid deliveries with recorded time and outcome |
| Pro feature | the same paid bottleneck appears in multiple deliveries |
| Subscription | customers repeatedly need the workflow, not just one-off editing |

Until those rows are supported, the correct product is the small, honest,
open-source core plus a manually delivered service.
