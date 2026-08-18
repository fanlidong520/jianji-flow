# jianji-flow v0.3 Usability Design

## Goal

v0.3 should make `jianji-flow` easier to try, easier to diagnose, and easier to
use for a real home-product short-video draft.

The goal is not to add more editing features. The goal is to reduce the distance
from "I have some clips" to "I know whether this can produce a useful rough
cut, and I know what to fix next."

## Current Judgment

v0.2 is a reliable technical base, but it is not yet "best usable":

- It can render a playable video with machine voiceover and burned-in captions.
- It has review artifacts, safety checks, tests, CI, and a public release.
- It still expects users to understand too many setup details.
- It relies heavily on asset filenames for matching.
- It does not yet explain asset problems in plain, actionable language.
- Its primary command is too long for first-time users.

v0.3 should optimize for fast real use, not for feature breadth.

## Product Principle

Keep the user path narrow:

```text
check environment
-> try a demo
-> inspect a real asset folder
-> run one quick draft
-> open one review page
-> know what to fix
```

If a feature does not help this path, it is out of scope for v0.3.

## Recommended Approach

Use the existing v0.2 pipeline as the engine and add a small usability layer on
top:

- `doctor`: inspect whether the machine and materials are ready.
- `demo`: create a sample run without requiring user materials.
- `quick`: run a real home-product draft with minimal arguments.
- Asset diagnosis: report missing or weak material roles before rendering.
- Review summary: make `review.html` and `review.md` say what a normal user
  should do next.

This approach is better than building a full editor UI now because the product
still needs stronger proof that the command-line workflow solves a real content
problem. It is also better than adding smarter matching first because users need
clear setup and diagnosis before matching quality can be judged fairly.

## Target User

The primary v0.3 user is a creator or operator making home-product commerce
short videos.

They can prepare a reference video and a local folder of video clips, but they
should not need to understand schemas, JSON artifacts, FFmpeg options, or the
internal five-part timeline model.

## User-Facing Commands

### `jianji-flow doctor`

Purpose: tell the user whether the local machine and input folder are ready.

Expected behavior:

- With no paths, check global environment:
  - Python version.
  - FFmpeg availability.
  - ffprobe availability.
  - Windows local Chinese TTS availability.
  - Writable output directory behavior using a temporary local check.
- With `--reference`, `--assets`, and optional `--script`, also inspect material
  readiness:
  - Reference video exists and is decodable.
  - Asset directory exists and contains decodable videos.
  - Candidate clips have enough total duration.
  - Product roles are covered when filenames expose role hints.
  - Output explains likely blockers in plain language.

The output should be text-first and short. It should end with one of:

- `Ready to run quick draft`
- `Can run, but review carefully`
- `Not ready`

### `jianji-flow demo`

Purpose: let a new user see the current output without preparing assets.

Expected behavior:

- Generate local synthetic fixtures.
- Run the product sample.
- Open no external service and download nothing.
- Print the paths to:
  - `remix.mp4`
  - `review.html`
  - `contact-sheet.png`
- Use a predictable work directory unless the user provides `--work-dir`.

Success means a user can see the current video experience before investing time
in collecting materials.

### `jianji-flow quick`

Purpose: run the most common real task with the shortest useful command.

Default behavior:

- Mode defaults to `product`.
- Target width, height, and FPS default to the reference video.
- Work directory defaults to `out/quick-<timestamp>` if not provided.
- Script is optional.
- If no script is provided, use a default home-product commerce script based on
  the five product roles:
  - hook
  - pain
  - feature
  - evidence
  - cta

Minimum intended command:

```powershell
jianji-flow quick --reference path\to\reference.mp4 --assets path\to\assets
```

`quick` should run `doctor`-style material checks first. If blockers exist, it
should stop before rendering and write a diagnosis report. It should not force a
bad render just to produce an MP4.

## Asset Diagnosis

v0.3 should introduce a small diagnosis model for product materials.

Required product roles:

- `hook`: opening or result preview.
- `pain`: problem scene.
- `feature`: product feature or product close-up.
- `evidence`: usage, before-after, or demonstration.
- `cta`: ending, product packshot, or reminder.

Role evidence can come from filename keywords first. v0.3 does not need full
vision-language matching.

Diagnosis status per role:

- `ready`: at least one likely clip exists and has enough duration.
- `weak`: a clip exists but evidence is fallback or duration is short.
- `missing`: no likely clip exists.

Run-level diagnosis:

- `pass`: all roles ready.
- `warning`: one or more roles weak, but no role missing.
- `fail`: at least one role missing, no decodable assets, or no asset can satisfy
  segment duration.

The user-facing message should be actionable:

- "Missing evidence clip: add a video showing the product being used."
- "Weak hook clip: rename an opening/result clip with `hook` or `opening`."
- "Asset too short: this clip is shorter than the target segment."

## Review Page Improvements

The current review page is useful for inspection but still technical. v0.3
should add a plain-language summary at the top.

Top summary fields:

- Overall decision:
  - `Usable rough cut`
  - `Needs review`
  - `Do not use yet`
- Main reason.
- Next action.

Examples:

- "Usable rough cut: all five roles have matched assets. Watch captions and
  product accuracy before publishing."
- "Needs review: evidence segment used fallback matching. Add a clearer
  demonstration clip if the segment looks wrong."
- "Do not use yet: missing pain and evidence clips. Add problem and demo clips,
  then rerun quick."

The page should still include the video, contact sheet, segment table, warnings,
and file paths for auditability.

## Generated Script Behavior

If the user does not provide a script for `quick --mode product`, v0.3 should use
a simple default script rather than failing.

Default script style:

- Short Chinese commerce captions.
- Neutral home-product wording.
- No unsupported product claims.
- No price, guarantee, medical, or absolute-performance promises.

This is a fallback only. The output should clearly say:

"No script was provided, so jianji-flow used a generic home-product script.
Replace it with your own product-specific copy for publishing."

## Non-Goals

v0.3 does not include:

- Jianying or CapCut draft export.
- A desktop editor UI.
- Online asset search.
- AI-generated product footage.
- Voice cloning.
- Music, sound effects, or beat-sync editing.
- Full vision-language semantic matching.
- Auto-publishing.
- Claims that the output is ready to publish without human review.

## Architecture

Keep the existing v0.2 run pipeline intact:

```text
reference probe
-> asset scan
-> segment plan
-> matching
-> schema validation
-> semantic validation
-> voiceover and captions
-> render
-> review artifacts
```

Add a usability layer before and after the existing engine:

```text
doctor/demo/quick command
-> environment diagnosis
-> material diagnosis
-> existing v0.2 run engine when allowed
-> plain-language review summary
```

Suggested modules:

- `environment.py`: checks FFmpeg, ffprobe, Python, and local TTS readiness.
- `asset_diagnosis.py`: evaluates product role coverage and material readiness.
- `quickstart.py`: provides default quick command behavior and fallback scripts.
- `review_summary.py`: converts technical review data into user-facing next
  actions.

These modules should expose small data dictionaries that can be serialized into
diagnostic JSON and rendered in markdown or HTML.

## Error Handling

`doctor` should not crash for normal setup problems. It should report them.

`quick` should stop before rendering when:

- Reference video is missing or undecodable.
- Asset directory is missing.
- No decodable video assets exist.
- Required product roles are missing and no fallback render is explicitly
  requested.
- Windows local TTS is unavailable for the default voiceover path.

`quick` may continue with warning when:

- Some role matches are weak but present.
- No script was provided and generic script fallback is used.
- Role coverage is inferred from fallback filenames.

Every failed run should still write a short report in the work directory when
the work directory can be created.

## Testing Strategy

Add tests before implementation.

Core tests:

- `doctor` reports missing TTS without crashing.
- `doctor` reports FFmpeg and ffprobe status.
- Material diagnosis marks all five product roles ready for well-named assets.
- Material diagnosis marks missing roles as fail.
- `demo` creates a runnable sample and reports key output paths.
- `quick` can run with only reference and assets when assets are sufficient.
- `quick` uses the generic script only when no script is provided.
- `quick` stops before rendering when required roles are missing.
- Review summary maps pass, warning, and fail states to plain next actions.

Regression tests:

- Existing `run` command behavior remains available.
- v0.2 output artifacts are still produced for full runs.
- Failure paths do not leave stale success artifacts.
- Linux CI does not require Windows local TTS smoke tests.
- Windows local smoke and P0 runners still exercise real TTS and rendering.

## Real-Use Validation

v0.3 is not accepted only because tests pass.

Manual validation must include at least ten runs:

- 3 synthetic fixture runs.
- 3 home-product asset-folder variations with clear filenames.
- 2 home-product asset-folder variations with weak or messy filenames.
- 1 no-script quick run.
- 1 intentionally incomplete asset folder.

For each run, record:

- Command used.
- Whether the user would know the next action within 30 seconds.
- Whether `review.html` makes the output decision clear.
- Whether the result is a usable rough cut, needs review, or should not be used.
- What material or UX problem remains.

## Acceptance Criteria

v0.3 is done when:

- A new user can run a demo with one command.
- A normal home-product quick run needs only one main command.
- A no-script product quick run produces a generic but honest script.
- Missing or weak materials are reported before a misleading render.
- The review page gives a clear decision and next action.
- Existing v0.2 functionality and safety checks still pass.
- Local validation passes:
  - full pytest suite
  - smoke runner
  - P0 runner
- GitHub Actions CI passes.
- At least ten validation runs are recorded with outcomes.

## Development Split

- Main controller: own the user flow, acceptance criteria, and final validation.
- Luna-style worker: implement `doctor`, `demo`, and `quick` command plumbing.
- Sol-style reviewer: review diagnosis correctness, failure honesty, and stale
  artifact behavior.
- A second reviewer should inspect generated review pages and at least a sample
  of rendered outputs before release.

## Release Rule

Do not publish v0.3 until the usability validation record exists.

Release notes must say:

- v0.3 improves setup, diagnosis, quick start, and review clarity.
- It is still a preview-video workflow, not a full editing application.
- Human review is still required before publishing.
