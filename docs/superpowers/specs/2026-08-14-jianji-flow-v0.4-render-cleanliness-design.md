# jianji-flow v0.4 Render Cleanliness Design

## Problem

The previous renderer added opaque top and bottom `drawbox` filters to protect
captions from source-platform residue. On real vertical material this created
visible dark bands even when the crop had already removed most of the residue.
The result looked like a template overlay and reduced trust in the remix.

## Decision

- Keep the existing center crop and fill-frame scaling.
- Remove the default full-frame top and bottom masks from the render filter.
- Keep caption readability through the existing ASS outline, shadow, and safe
  vertical margin.
- Keep source preflight as the place that detects and reports platform chrome or
  old subtitles. The renderer must not hide a risky source by default.

## Invariants

- The reference video is still excluded from every rendered input.
- Output dimensions, frame rate, audio strategy, caption files, and semantic
  path checks remain unchanged.
- Warning and fail decisions still come from source preflight and artifact
  review; removing masks must not turn a risky source into a pass.
- A clean source must not gain artificial horizontal bands from the renderer.

## Verification

- Red test: the vertical render filter must contain no `drawbox` mask.
- Focused render tests pass.
- Real opaque-filename home-product run `run-v35f` was rendered and inspected;
  the gray top and dark bottom bands disappeared while captions remained legible.
- Full tests, smoke, and P0 pass before commit.
