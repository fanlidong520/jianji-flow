# jianji-flow v0.2 Experience Design

## Goal

v0.2 should turn the current silent preview pipeline into a small but complete
video experience: visible captions, machine voiceover, and a human review page.

The purpose is not to build a full editing app yet. The purpose is to answer one
practical question: can a user give jianji-flow a reference video, a topic, and
source clips, then get an auditable short video that is worth reviewing?

## Current Evidence

The v0.1 pipeline can already:

- Read a reference video and use its duration and target format.
- Scan local video assets.
- Build a five-part product sequence.
- Match clips by role.
- Render a vertical MP4.
- Write `manifest.json`, `recipe.json`, `matches.json`, `captions.srt`, and
  `review.md`.

The first visual fixture was too weak because it only showed changing color
blocks. The revised home-cleaning trial fixed that by using visible scenes and
Chinese text, but it still had no real voiceover and no in-video captions.

## Recommended Approach

Build v0.2 as an experience layer on top of the existing v0.1 contracts.

This is the smallest useful next step because it keeps the existing safety model
while making the output feel like an actual short video, not just a technical
render.

The other options are less suitable right now:

- Better semantic matching is important, but silent output still feels unfinished.
- A desktop editor UI would look more product-like, but the core video experience
  is not mature enough yet.

## Scope

v0.2 includes:

- Machine voiceover generated from the script or segment captions.
- Burned-in captions in `remix.mp4`.
- A local `review.html` page with the video, segment table, selected assets,
  confidence, warnings, and manual review checklist.
- A contact sheet image that covers all rendered segments.
- Updated tests and smoke checks proving the above outputs are present and
  inspectable.

## Non-Goals

v0.2 does not include:

- Jianying or CapCut draft export.
- A full desktop editing application.
- Automatic online material search.
- Publishing to any platform.
- Human-quality voice cloning.
- Music selection or beat-synced editing.
- Advanced vision-language semantic matching.

## User Flow

1. The user provides a reference video path and a local asset directory.
2. The user chooses `product` or `talking-head`.
3. If no script is supplied, Codex can help create a short script before running
   the skill.
4. jianji-flow creates the timeline and matches assets as v0.1 already does.
5. jianji-flow generates voiceover audio from the captions.
6. jianji-flow renders `remix.mp4` with burned-in captions and voiceover.
7. jianji-flow writes `review.md`, `review.html`, and a contact sheet.
8. The user watches the MP4 and opens the review page to decide what to improve.

## Architecture

The existing pipeline remains the spine:

```text
input validation
-> media scan
-> segment plan
-> asset matching
-> schema validation
-> semantic validation
-> captions
-> voiceover
-> render
-> review report
-> review page
```

### Voiceover

Add a voiceover module that takes the script-derived captions and creates one
audio file for the full video.

For v0.2, use a local machine voice first. On Windows this can use the built-in
speech engine when available. If no suitable local voice exists, the run should
fail with a clear message instead of silently producing a mute video.

New output:

- `voiceover.wav`

The voiceover does not need to sound human. It does need to be audible, complete,
and roughly aligned with the rendered video duration.

### Captions

Keep `captions.srt` as an editable subtitle file and add burned-in captions to
`remix.mp4`.

The render step should use a font known to support Chinese on Windows when
available, such as Microsoft YaHei. If a font cannot be found, the run should
produce a warning or failure that explains the missing font problem.

New or updated outputs:

- `captions.srt`
- `captions.ass` when the renderer needs ASS styling for burn-in
- `remix.mp4` with visible captions

### Review Page

Add a static local HTML review page. It should require no server.

The page should show:

- The rendered video.
- The contact sheet.
- Segment start and end times.
- Segment caption.
- Selected asset path.
- Confidence and evidence.
- Warnings and failures.
- Manual review checklist.

New outputs:

- `review.html`
- `contact-sheet.png`

### Render Audio Strategy

v0.2 should introduce a clearer audio strategy:

- `voiceover-only`: render the generated voiceover as the main audio track.
- `voiceover-with-source-bed`: optional later behavior that keeps source audio
  quietly under the voiceover.

The v0.2 default is `voiceover-only`.

## Data Contract Changes

`recipe.json` will add:

- `audio_strategy: "voiceover-only"`
- `voiceover_path`
- `caption_burn_in: true`

`review.md` and `review.html` should include all new output paths.

The manifest should not treat generated voiceover as a visual asset. It remains a
render artifact.

## Error Handling

The run should fail clearly when:

- Voice generation is requested but no local TTS engine is available.
- The generated voiceover file is missing, empty, or unreadable.
- Caption burn-in fails.
- The final MP4 has no audio stream.
- The final MP4 has no visible frame content.

The run may complete with warning when:

- Captions are present but the selected font had to fall back.
- Voiceover duration differs noticeably from the target video duration, but the
  audio was padded or trimmed safely.
- Asset matching is still based on filename roles.

## Testing

Add focused tests for:

- Voiceover artifact creation.
- Render command includes voiceover when `voiceover-only` is selected.
- Final MP4 has an audio stream.
- Caption files stay UTF-8.
- Caption burn-in path handling on Windows-style paths.
- Review HTML includes video path, contact sheet, captions, and match evidence.
- Failed voiceover generation does not leave a stale successful `remix.mp4`.

Add smoke validation for:

- Product sample produces `voiceover.wav`, `captions.srt`, `remix.mp4`,
  `review.md`, `review.html`, and `contact-sheet.png`.
- Extracted frames show visible non-plain content.
- Review report status is `pass` or honest `warning`, never fake success.

## Acceptance Criteria

v0.2 is done when:

- A home-product sample can generate a playable MP4 with visible captions and
  audible machine voiceover.
- The MP4 duration is close to the reference duration.
- The review page opens locally and shows enough information for the user to
  judge every segment.
- The full regression suite passes.
- A manual frame check confirms the video is not just background changes.
- Known limitations are documented in README and SKILL.md.

## Development Split

- Luna: implement voiceover, caption burn-in, review page, and smoke artifacts.
- Sol: review contracts, safety checks, path handling, stale-output behavior,
  and tests.
- Main controller: run final validation, inspect sample frames, explain the
  experience honestly to the user, and decide whether the repo is ready to push.

## Implementation Checks

- Before implementing voiceover, check which local TTS voices are available on
  the user's Windows machine.
- v0.2 will generate one full voiceover file, not one file per segment.
- v0.2 will keep source audio muted and use `voiceover-only`.

Segment-level voice timing and source-audio mixing are future improvements after
the first audible sample is reviewed.
