# jianji-flow

`jianji-flow` is an open-source Codex skill for auditable automatic preview-video workflows.

It takes a reference video, a local asset directory, and an optional script, then creates a reviewable short-video draft with machine voiceover, burned-in captions, and a local review page.

## What v0.2 Does

- Builds a structured timeline for `product` or `talking-head` videos.
- Scans local video assets and writes `manifest.json`.
- Matches timeline segments to assets and writes `matches.json`.
- Writes the authoritative timeline to `recipe.json`.
- Generates `captions.srt` and `captions.ass`.
- Generates `voiceover.wav` with a local Windows Chinese TTS voice when available.
- Renders `remix.mp4` with burned-in captions and voiceover audio.
- Writes `contact-sheet.png` with one frame per timeline segment.
- Writes `review.md` and `review.html` for manual inspection.

## What v0.2 Does Not Do

- It does not create Jianying or CapCut draft projects.
- It does not build a full desktop editing application.
- It does not search online for assets.
- It does not publish videos.
- It does not preserve source audio by default.
- It does not generate music, effects, or beat-synced edits.
- It does not guarantee semantic matching beyond the current auditable matching evidence.

## Contract Note

The package is v0.2.0, but the JSON recipe contract still uses `"version": "0.1"` for compatibility with the v0.1 schema. The v0.2 experience adds optional fields such as:

- `audio_strategy: "voiceover-only"`
- `voiceover_path`
- `caption_burn_in: true`

## Requirements

- Python 3.10+
- FFmpeg and ffprobe
- Windows local TTS for default voiceover generation

Check the environment:

```powershell
python scripts/check_env.py
```

## Quick Start

Generate local synthetic fixtures:

```powershell
python scripts/generate_fixtures.py --output fixtures
```

Run the product sample:

```powershell
python -m jianji_flow run --mode product --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --work-dir out\scenario-a-product --target-width 320 --target-height 180 --target-fps 12
```

Run the talking-head sample:

```powershell
python -m jianji_flow run --mode talking-head --reference fixtures\scenario-b-talking\reference.mp4 --assets fixtures\scenario-b-talking\assets --script fixtures\scenario-b-talking\transcript.txt --work-dir out\scenario-b-talking --target-width 320 --target-height 180 --target-fps 12
```

## Outputs

- `manifest.json`: local asset inventory.
- `recipe.json`: authoritative timeline.
- `matches.json`: selected assets, confidence, and evidence.
- `captions.srt`: editable subtitle file.
- `captions.ass`: styled subtitle file used for burn-in.
- `voiceover.wav`: generated machine voiceover.
- `remix.mp4`: rendered preview video.
- `contact-sheet.png`: one representative frame per segment.
- `review.md`: review status and checklist.
- `review.html`: local visual review page.

## Validation

```powershell
python -m pytest -q
python scripts/run_smoke.py
python scripts/run_p0.py
```

Latest local result:

- `python -m pytest -q` -> 171 passed
- `python scripts/run_smoke.py` -> smoke passed
- `python scripts/run_p0.py` -> p0 passed

## Safety Rules

- Reference video picture and audio are never copied into `remix.mp4`.
- URL, protocol, protocol-relative, and network paths are rejected.
- Outputs must stay inside the requested work directory.
- Blocking failures remove stale success artifacts.
- `review.md` must report failures and warnings honestly.

## License

MIT
