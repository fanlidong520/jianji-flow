# Product-Grade Findings

## 2026-08-13 Reset

The user explicitly raised the bar: `jianji-flow` must become genuinely useful before open source, not a repository published for its own sake.

The product definition changed from "generate a preview video" to "generate a trustworthy, reviewable rough cut that clearly saves editing work."

A video that only changes voiceover while looking like the source video is a product failure.

## Current Evidence

`out/real-material-remix-v7` proves the pipeline can now produce visible remixing:

- it uses the normal `quick` path;
- it retimes the timeline to the generated voiceover;
- it applies real center crop and fill-frame scaling;
- it burns readable UTF-8 Chinese captions;
- it reports remaining platform UI or old subtitle risk as a warning.

It is not publish-ready:

- the source material was cut from one already-posted video;
- old subtitles and embedded text remain in at least one segment;
- material quality problems are discovered after rendering, not early enough;
- different filenames are not proof of true source diversity.

## Product Risks

- A false `pass` is worse than a failed run.
- Contact-sheet-only validation is not enough; each segment needs multi-frame sampling.
- Severe or repeated platform UI warnings should become `fail`.
- Material diagnosis must tell users what to replace before rendering.
- README and Chinese docs need cleanup before public launch.

## Product Decisions

- Do not call v7 a final demo.
- Keep v7 as an evidence sample for visible rough-cut remixing.
- Open-source MVP should be positioned as "role-based material assembly" instead of "reference video decomposition" until real shot/beat extraction exists.
- Filename role matches should not be presented as high visual understanding confidence.
- Public launch requires blind testing with users who did not participate in development.
- Next engineering priority: preflight material diagnosis and stricter review escalation.
- Next product priority: first-time usage and failure guidance.
- Next business priority: service-led paid validation before SaaS.

## Product Review Findings From Parallel Audit

- Public release is not recommended yet.
- v7 proves the pipeline can run and visibly remix, but does not prove ordinary creators will find it easy, time-saving, or trustworthy.
- The product promise should be narrowed to: clean product clips plus short script -> reviewable product rough cut.
- Talking-head mode, general reference decomposition claims, music, effects, publishing, Jianying draft generation, and desktop UI should remain out of MVP until validated.
- Launch bar should include at least three independent clean real-material packs and one dirty-material failure case.
- First-time usability should be tested with people who only read the README.

## Commercialization Direction

Open source the useful local-first CLI and skill.

Paid paths should come later:

- niche templates and validation packs;
- setup/customization services;
- batch workflow UI;
- private deployment for teams;
- hosted or desktop wrapper only after real users prove repeated demand.
