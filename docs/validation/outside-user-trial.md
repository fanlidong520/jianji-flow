# Outside User Trial

This is the smallest reproducible trial for a person who has not worked on
`jianji-flow`. It measures whether the README path is clear and whether the
output is visibly re-edited, not whether the person agrees with the code.

## Before Starting

- Use Windows with Python 3.10+, FFmpeg, and ffprobe.
- Install the repository and the optional online narration backend:

```powershell
python -m pip install -e ".[edge-tts]"
```

- Start a timer before installation. Do not give the tester private developer
  instructions or edit their output for them.

## Ten-Minute Trial

Run the built-in demo first. It creates synthetic local fixtures and does not
upload media:

```powershell
jianji-flow doctor --work-dir out\trial-doctor
jianji-flow demo --work-dir out\trial-demo
```

Then open:

- `out\trial-demo\review.html`
- `out\trial-demo\remix.mp4`
- `out\trial-demo\contact-sheet.png`

The demo is a rough-cut demonstration. A `warning` status is expected when
the run uses filename roles without a visual selection file; the tester should
judge the visible result and the warnings, not treat `warning` as publish-ready.

## Optional Real-Material Trial

If the tester has a reference video and clean local clips, use:

```powershell
jianji-flow quick --reference path\reference.mp4 --assets path\assets --script path\script.txt --tts-provider auto --work-dir out\trial-real
```

Do not upload the input media to this repository. Record whether the clips are
independent originals or copies from one mother video. If `doctor` reports no
usable narration provider, pass a local WAV with `--voiceover` instead.

## Feedback Record

Generate a private trial template before the tester starts:

```powershell
jianji-flow outside-trial --id tester-01 --output-dir out\outside-trial-tester-01
```

This writes `outside-user-trial.md`, `outside-user.entry.json`, and
`outside-trial.json`. The generated entry is intentionally not counted by the
release gate yet:

```json
{
  "id": "tester-01",
  "readme_quickstart": false,
  "completed_in_minutes": null,
  "visible_remix": null,
  "review_status": "",
  "blocked_step": "",
  "notes": ""
}
```

After the tester actually uses the README path, copy the completed entry into a
private evidence ledger or issue, using a stable pseudonymous id and no personal
media. A completed passing-looking record has this shape:

You can generate that entry after the demo artifacts exist:

```powershell
jianji-flow outside-trial-result --id tester-01 --demo-dir out\trial-demo --completed-in-minutes 8 --visible-remix yes --readme-quickstart --output-dir out\outside-trial-result-tester-01
```

This command checks that `review.md`, `review.html`, `remix.mp4`, and
`contact-sheet.png` exist and are non-empty. It does not decide whether the
result is visibly re-edited; `--visible-remix yes` must come from the tester's
answer.

```json
{
  "id": "tester-01",
  "readme_quickstart": true,
  "completed_in_minutes": 8,
  "visible_remix": true,
  "review_status": "warning",
  "blocked_step": "",
  "notes": "The contact sheet made the changed shots obvious."
}
```

Ask only these questions:

1. Did you reach a playable MP4 without developer help?
2. Did the contact sheet make it obvious that the pictures changed?
3. What was the first confusing or blocking step?
4. Would you use this on another video?

Record the raw answer and exact command used. Do not turn a positive opinion
into a release pass unless the output is playable and the tester actually used
the README path.
