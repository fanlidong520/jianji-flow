# jianji-flow v0.5 Multi-shot Design

## Goal

Make the visible edit feel like a real remix instead of five long source windows
under a new voiceover. A story segment remains the unit for narration and
captions, but its picture may be assembled from multiple short source shots.

This milestone is structural editing, not semantic understanding. Scene-change
detection may propose boundaries; Codex visual review remains the authority for
whether a shot supports the spoken claim.

## Scope

- Add an opt-in `--multi-shot` mode to `run` and `quick`.
- Detect bounded scene-change boundaries inside each selected source window.
- Store optional `shots` on a match while keeping the existing top-level match
  fields backward compatible.
- Render all shots in order while keeping the recipe's five story segments,
  captions, voiceover, and total duration unchanged.
- Write a `shot-plan.json` audit artifact and expose shot count and fallback
  warnings in the review output.
- Write a `shot-contact-sheet.png` audit artifact with one labeled frame per
  final rendered shot.
- Keep the current one-window path as the default until real-material checks
  show that multi-shot mode is consistently better.

## Data Flow

1. Build the normal five-segment plan and select assets/windows as today.
2. When `--multi-shot` is present, run FFmpeg scene detection over each selected
   source window with a bounded threshold, minimum shot duration, and maximum
   shot count.
3. If usable boundaries are found, attach ordered `shots` to that match. Each
   shot records asset identity, source path, source range, and a structural
   boundary reason. If detection fails or finds no safe boundary, keep one shot
   and record a warning in `shot-plan.json`.
4. Validate every shot against the manifest, asset root, reference exclusion,
   source range, and exact segment-duration sum before voiceover or render.
5. Flatten shots only at render time. Captions continue to use the parent story
   segment so narration and text are not duplicated.
6. Retiming scales shot durations within each parent segment and adjusts the
   last shot to preserve exact duration.
7. Generate the shot contact sheet from the final retimed recipe and matches,
   so the visual audit board cannot drift from the rendered timeline.

## Safety Invariants

- No shot may reference the reference video, a URL, a protocol path, or a file
  outside the scanned asset directory.
- Each shot range must be inside its manifest asset duration.
- Ordered shot durations must sum exactly to the parent segment duration.
- A failed detector cannot produce a partial or stale success artifact.
- Structural boundaries and frame-difference scores must never be reported as
  proof that a shot matches the script.
- A segment with no safe boundary remains renderable as one source window but
  carries an explicit fallback warning.

## Acceptance Checks

- Existing default-mode tests and outputs remain unchanged except for the new
  optional audit file when multi-shot mode is used.
- Unit tests cover boundary filtering, minimum duration, max-shot bounds,
  detector failure fallback, exact duration sums, and stale artifact cleanup.
- Render tests prove that a parent segment with multiple shots produces multiple
  inputs and one continuous output with the expected duration and audio.
- A real opaque-filename home-product run produces more than five visual shots
  only when the source contains safe boundaries; otherwise it honestly reports
  the fallback count.
- The real run is judged by the contact sheet, the new shot plan, and the
  playable remix. No pass claim is made from structural metrics alone.

## Non-goals

- No automatic semantic claim matching in this milestone.
- No music, effects, transitions, beat sync, or editor draft export.
- No default behavior change until the real-material A/B comparison is positive.
