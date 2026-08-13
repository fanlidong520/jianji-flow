# Commercialization Strategy

`jianji-flow` should be open source because trust and workflow adoption matter.
Commercialization should not depend on hiding the core workflow.

## Open-Source Positioning

Open-source project:

- local-first automatic rough-cut workflow;
- auditable recipes, matches, captions, review reports;
- safe defaults and honest warnings;
- useful for creators, agencies, and AI workflow builders.

The free project should be genuinely useful.
If the free version is weak, monetization will not be trusted.

## Who Would Pay

Likely paid users:

- short-video creators who batch produce product videos;
- small e-commerce sellers without editing staff;
- agencies managing many product clips;
- AI workflow builders who need a reliable video assembly backend;
- teams that want private/local media processing.

## Monetization Paths

Recommended path:

1. Open-source CLI and Codex skill.
2. Service-led setup for one concrete niche, delivering a validated local workflow and accepted rough cuts.
3. Paid templates and validation packs for specific niches.
4. Hosted or desktop wrapper for non-technical users.
5. Team features: batch processing, shared brand presets, review queues.
6. Services: customization, private deployment, agency workflow design.

Avoid early monetization that weakens trust:

- do not hide basic rough-cut generation behind a paywall;
- do not claim "one-click viral video";
- do not sell before real user workflows prove repeated value.

## First Paid Offer

The first realistic paid offer should be service-led:

"I help you build a repeatable local AI editing workflow for your product-video niche."

Deliverables:

- material naming rules;
- product script template;
- validated `jianji-flow` workflow;
- three manually accepted rough cuts, including review reports and contact sheets;
- 1-2 custom presets for the user's content type.

This can validate demand before building a polished SaaS.

## Open-Core Boundary

Keep these free and open:

- local single-video rough-cut generation;
- open `manifest.json`, `recipe.json`, `matches.json`, caption files, and review reports;
- material diagnosis, source-preflight warnings, and story-support warnings;
- segment repair through `fixes.template.json` and `--fixes`;
- safety gates that prevent false pass or reference-video leakage.

Paid offerings can sit around the workflow:

- niche-specific templates, validation packs, and example material rules;
- non-technical desktop or hosted UI;
- batch queues, team presets, review history, and collaboration;
- private deployment, custom rules, and workflow onboarding.

Do not monetize by hiding risk reports or weakening the free workflow. Trust is the product.

## Business Metrics

Track:

- time from raw clips to reviewable rough cut;
- number of manual editing steps saved;
- percentage of outputs that reach pass/warning/fail;
- user corrections needed per video;
- repeat usage after the first successful output;
- willingness to pay for setup, templates, or batch UI.

## Commercialization Gate

Do not build paid SaaS until at least one real user outside this workspace:

- runs the workflow on their own material;
- produces a rough cut they would continue editing or publish after small changes;
- asks for repeated use, customization, or batch support;
- is willing to pay for saved time or setup.
