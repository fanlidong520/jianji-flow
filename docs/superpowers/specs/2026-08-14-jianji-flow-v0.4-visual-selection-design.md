# jianji-flow v0.4 Visual Selection Design

## Goal

Make the first meaningful visual-editing loop work when source filenames carry
no semantic labels. The local pipeline will produce auditable candidate windows
and frames; Codex will inspect those frames and choose a candidate using the
script and story role. The selected candidate will be validated, rendered, and
shown in the review output with explicit visual-review evidence.

This is a Codex-assisted visual selection workflow. It is not a claim that a
local brightness, edge, or frame-difference score understands product meaning.

## Product Boundary

In scope:

- Extract a bounded set of candidate source windows for every planned segment.
- Save three representative frames, source ranges, asset ids, and SHA-256
  fingerprints for every candidate.
- Generate a visual candidate sheet and a selection template that do not depend
  on role words in filenames.
- Accept a filled selection file, validate candidate identity, asset identity,
  duration, and source range, then apply it to `matches.json`.
- Record `visual-review:<candidate_id>` evidence and show the selection in the
  storyboard and review report.
- Let `quick` continue with a visual selection file even when filename-based
  material diagnosis would otherwise stop for missing roles.

Out of scope:

- Pretending local frame sharpness or color statistics are semantic matching.
- A new desktop editor, Jianying export, music, effects, or publishing.
- Requiring a cloud API or a heavyweight vision model for the base package.
- Automatically marking an uninspected candidate as visually verified.

## User Flow

```text
quick or visual-review
  -> scan assets and build segment durations
  -> create visual-candidates.json, visual-candidate-sheet.png,
     visual-selection.template.json
  -> Codex inspects the candidate frames and fills visual-selections.json
  -> quick --visual-selections visual-selections.json
  -> validate selected candidate against the current asset folder
  -> render and write visual-review evidence
  -> inspect review.html and the before/after storyboard
```

The selection file contains only candidate ids plus a short reason and reviewer
type. The candidate manifest remains the source of truth for paths and ranges.
This prevents a reviewer from silently changing a path or time range that was
not shown in the visual board.

## Architecture

### `visual_candidates.py`

Expose small functions:

- `build_visual_candidate_manifest(segments, assets, work_dir) -> dict`
- `write_visual_candidate_artifacts(manifest, segments, work_dir) -> dict`
- `load_visual_selection(path) -> dict`
- `apply_visual_selections(segments, matches, assets, selection, candidate_manifest) -> dict`

Candidate generation is deterministic. For each segment duration, it samples
start, middle, and end windows from duration-compatible assets, caps the total
candidate count per segment, and extracts three frames inside each selected
window. It may rank candidates by frame information for display order, but that
rank is explicitly non-semantic and cannot create visual-review evidence.

Each candidate includes:

- `candidate_id`, `segment_id`, `asset_id`, `asset_path`
- `source_start_ms`, `source_end_ms`, `asset_duration_ms`
- three frame paths, sample times, and frame SHA-256 values
- non-semantic quality metrics and extraction warnings

### CLI

Add a `visual-review` command for generating the board without rendering. Add
`--visual-selections` to `run` and `quick`. A filled selection file must name a
candidate manifest and must contain a non-empty candidate id for every planned
segment. Invalid, stale, missing, too-short, or cross-segment candidates fail
before voiceover and rendering; stale success artifacts are removed.

When `quick` receives `--visual-selections`, filename diagnosis remains visible
but does not block a valid visual selection. Without that file, the existing
filename/duration diagnosis behavior remains unchanged.

### Review output

`matches.json` stores the selected source window and
`visual-review:<candidate_id>` evidence. `review.md` and `review.html` label
this as “Codex visual review” and show the candidate id, frame evidence, and
reviewer reason. The report must not describe this evidence as an objective
semantic score.

## Error Handling

- Missing candidate manifest: fail with the path and the next command.
- Unknown candidate id: fail and name the segment and id.
- Candidate belongs to another segment: fail before rendering.
- Asset id, path, digest, or duration no longer matches the scanned asset: fail
  and ask for a fresh visual board.
- Source range outside the current asset: fail before rendering.
- Blank reviewer reason or blank candidate id: fail for a filled selection file.
- Extraction failure: keep the candidate marked unavailable and never allow it
  to be selected.

## Testing Strategy

Write tests before implementation for:

- deterministic candidate windows and bounded candidate counts;
- candidate frame extraction and SHA-256 recording with a fake extractor;
- selection schema and candidate-manifest binding;
- unknown, cross-segment, stale-asset, short-range, and unavailable-candidate
  rejection;
- successful selection updates source path/range and adds visual-review
  evidence;
- `quick` still stops on missing filename roles without selections but proceeds
  with a valid visual selection;
- review markdown and HTML expose visual-review evidence and never call quality
  metrics semantic proof;
- failed selection runs remove stale render artifacts.

## Acceptance Criteria

1. The opaque-filename baseline produces a visual candidate board instead of
   requiring role words to generate candidates.
2. A Codex visual selection for all five home-product segments renders a video
   whose `matches.json` contains five validated visual-review selections.
3. The review page lets a non-technical reader see the selected asset, exact
   source window, candidate frames, and why the candidate was chosen within 30
   seconds.
4. Invalid or stale selections fail before rendering and do not leave a stale
   success video.
5. Full tests, smoke, and P0 pass; the non-semantic real-material run is recorded
   as a visual-review validation, not mislabeled as autonomous semantic AI.
6. The README and SKILL state clearly that this is Codex-assisted visual
   selection and that human review remains required before publishing.
