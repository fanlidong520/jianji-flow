# jianji-flow v0.2 Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v0.2 experience layer: machine voiceover, burned-in captions, contact sheet, and a local review page.

**Architecture:** Keep the existing v0.1 pipeline and contracts as the spine. Add focused modules for voiceover, caption burn-in support, and review-page generation, then wire them through the CLI after schema and semantic validation.

**Tech Stack:** Python 3.10+, FFmpeg/ffprobe, pytest, JSON Schema, Windows local TTS through PowerShell/SAPI when available.

## Global Constraints

- v0.2 does not create Jianying or CapCut draft projects.
- v0.2 does not build a full desktop editing application.
- v0.2 does not search the web for materials or publish videos.
- v0.2 default audio strategy is `voiceover-only`.
- v0.2 generates one full `voiceover.wav`, not one file per segment.
- v0.2 keeps source audio muted.
- Reference video picture and audio must never be used in `remix.mp4`.
- All outputs must stay inside the requested work directory.
- Failed runs must not leave stale successful `remix.mp4`.

---

## File Structure

- Modify `schemas/recipe.schema.json`: allow v0.2 audio fields while keeping v0.1 compatibility.
- Modify `src/jianji_flow/matcher.py`: allow `build_recipe()` to include `voiceover_path` and `caption_burn_in`.
- Create `src/jianji_flow/voiceover.py`: create and validate a local machine voiceover artifact.
- Modify `src/jianji_flow/subtitles.py`: create ASS captions for FFmpeg burn-in while keeping SRT output.
- Modify `src/jianji_flow/render.py`: support caption burn-in and `voiceover-only` audio.
- Create `src/jianji_flow/contact_sheet.py`: extract representative frames into `contact-sheet.png`.
- Modify `src/jianji_flow/review.py`: add new outputs and generate `review.html`.
- Modify `src/jianji_flow/cli.py`: wire voiceover, ASS captions, rendering, contact sheet, and review page.
- Modify `scripts/run_smoke.py` and `scripts/run_p0.py`: assert v0.2 outputs.
- Modify `README.md` and `SKILL.md`: document the audible/captioned v0.2 flow and limits.
- Add tests in `tests/test_voiceover.py`, `tests/test_render.py`, `tests/test_review.py`, `tests/test_subtitles.py`, `tests/test_cli.py`, and `tests/test_contracts.py`.

---

### Task 1: Voiceover Contract And Local TTS

**Files:**
- Create: `src/jianji_flow/voiceover.py`
- Modify: `schemas/recipe.schema.json`
- Modify: `src/jianji_flow/matcher.py`
- Test: `tests/test_voiceover.py`
- Test: `tests/test_contracts.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: recipe dictionaries with `segments[*].caption` and `duration_ms`.
- Produces: `build_voiceover_text(recipe: dict) -> str`
- Produces: `create_voiceover(recipe: dict, output_path: Path, *, rate: int = 0) -> Path`
- Produces: `validate_voiceover(path: Path) -> None`
- Produces: `build_recipe(..., audio_strategy: str = "silent-preview", voiceover_path: Path | None = None, caption_burn_in: bool = False) -> dict`

- [ ] **Step 1: Write failing voiceover text tests**

```python
# tests/test_voiceover.py
from pathlib import Path

import pytest

from jianji_flow.voiceover import build_voiceover_text, validate_voiceover


def test_build_voiceover_text_joins_non_empty_segment_captions():
    recipe = {
        "segments": [
            {"caption": "第一句"},
            {"caption": "  "},
            {"caption": "第二句"},
        ]
    }

    assert build_voiceover_text(recipe) == "第一句\n第二句"


def test_build_voiceover_text_rejects_empty_script():
    with pytest.raises(ValueError, match="voiceover text"):
        build_voiceover_text({"segments": [{"caption": ""}]})


def test_validate_voiceover_rejects_missing_or_empty_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_voiceover(tmp_path / "missing.wav")

    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        validate_voiceover(empty)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_voiceover.py -q`

Expected: fail with `ModuleNotFoundError: No module named 'jianji_flow.voiceover'`.

- [ ] **Step 3: Implement minimal voiceover helpers**

```python
# src/jianji_flow/voiceover.py
from __future__ import annotations

import subprocess
from pathlib import Path


def build_voiceover_text(recipe: dict) -> str:
    captions = [
        str(segment.get("caption", "")).strip()
        for segment in recipe.get("segments", [])
        if str(segment.get("caption", "")).strip()
    ]
    text = "\n".join(captions)
    if not text:
        raise ValueError("voiceover text is empty")
    return text


def validate_voiceover(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.stat().st_size <= 0:
        raise ValueError(f"voiceover file is empty: {path}")


def create_voiceover(recipe: dict, output_path: Path, *, rate: int = 0) -> Path:
    text = build_voiceover_text(recipe)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    escaped_text = text.replace("'", "''")
    escaped_path = str(output_path).replace("'", "''")
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {rate}; "
            f"$s.SetOutputToWaveFile('{escaped_path}'); "
            f"$s.Speak('{escaped_text}'); "
            "$s.Dispose();"
        ),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "local TTS failed"
        raise RuntimeError(detail)
    validate_voiceover(output_path)
    return output_path
```

- [ ] **Step 4: Add schema and recipe tests**

```python
# tests/test_contracts.py
def test_recipe_allows_voiceover_only_outputs():
    data = valid_recipe()
    data["audio_strategy"] = "voiceover-only"
    data["voiceover_path"] = "work/voiceover.wav"
    data["caption_burn_in"] = True

    validate_recipe(data)


def test_recipe_voiceover_only_requires_voiceover_path():
    data = valid_recipe()
    data["audio_strategy"] = "voiceover-only"

    with pytest.raises(ValidationError):
        validate_recipe(data)
```

```python
# tests/test_matcher.py
def test_build_recipe_can_include_voiceover_and_caption_burn_in():
    recipe = build_recipe(
        "product",
        {"width": 1080, "height": 1920, "fps": 30},
        [segment],
        matches,
        voiceover_path=Path("work/voiceover.wav"),
        caption_burn_in=True,
        audio_strategy="voiceover-only",
    )

    assert recipe["audio_strategy"] == "voiceover-only"
    assert recipe["voiceover_path"] == "work/voiceover.wav"
    assert recipe["caption_burn_in"] is True
```

- [ ] **Step 5: Implement schema and matcher changes**

```json
// schemas/recipe.schema.json relevant changes
"audio_strategy": {"enum": ["silent-preview", "voiceover-only"]},
"voiceover_path": {"type": "string", "minLength": 1},
"caption_burn_in": {"type": "boolean"},
"allOf": [
  {
    "if": {"properties": {"audio_strategy": {"const": "voiceover-only"}}},
    "then": {"required": ["voiceover_path", "caption_burn_in"]}
  }
]
```

```python
# src/jianji_flow/matcher.py build_recipe signature and fields
def build_recipe(..., voiceover_path: Path | None = None, caption_burn_in: bool = False) -> dict:
    ...
    if voiceover_path is not None:
        recipe["voiceover_path"] = voiceover_path.as_posix()
    if caption_burn_in:
        recipe["caption_burn_in"] = True
```

- [ ] **Step 6: Run task tests**

Run: `python -m pytest tests/test_voiceover.py tests/test_contracts.py tests/test_matcher.py -q`

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/jianji_flow/voiceover.py src/jianji_flow/matcher.py schemas/recipe.schema.json tests/test_voiceover.py tests/test_contracts.py tests/test_matcher.py
git commit -m "Add voiceover contract"
```

---

### Task 2: Caption Burn-In And Voiceover Rendering

**Files:**
- Modify: `src/jianji_flow/subtitles.py`
- Modify: `src/jianji_flow/render.py`
- Test: `tests/test_subtitles.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `captions.srt`, `captions.ass`, `voiceover.wav`, `recipe["audio_strategy"]`.
- Produces: `ass_from_recipe(recipe: dict, *, width: int, height: int, font_name: str = "Microsoft YaHei") -> str`
- Produces: `write_ass(recipe: dict, output_path: Path, *, font_name: str = "Microsoft YaHei") -> None`
- Produces: `build_ffmpeg_plan(..., captions_path: Path | None = None, voiceover_path: Path | None = None) -> list[str]`

- [ ] **Step 1: Write failing ASS caption tests**

```python
# tests/test_subtitles.py
from jianji_flow.subtitles import ass_from_recipe, write_ass


def test_ass_from_recipe_contains_chinese_caption_and_style():
    recipe = {
        "target": {"width": 720, "height": 1280, "fps": 30},
        "segments": [{"start_ms": 0, "end_ms": 1200, "caption": "家里难刷角落"}],
    }

    ass = ass_from_recipe(recipe, width=720, height=1280)

    assert "[Script Info]" in ass
    assert "Microsoft YaHei" in ass
    assert "家里难刷角落" in ass


def test_write_ass_creates_utf8_file(tmp_path: Path):
    recipe = {
        "target": {"width": 720, "height": 1280, "fps": 30},
        "segments": [{"start_ms": 0, "end_ms": 1000, "caption": "可伸缩清洁刷"}],
    }
    output = tmp_path / "captions.ass"

    write_ass(recipe, output)

    assert "可伸缩清洁刷" in output.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_subtitles.py::test_ass_from_recipe_contains_chinese_caption_and_style tests/test_subtitles.py::test_write_ass_creates_utf8_file -q`

Expected: fail because `ass_from_recipe` and `write_ass` are missing.

- [ ] **Step 3: Implement ASS helpers**

```python
# src/jianji_flow/subtitles.py additions
def _format_ass_time(ms: int) -> str:
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    centiseconds = milliseconds // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def ass_from_recipe(recipe: dict, *, width: int, height: int, font_name: str = "Microsoft YaHei") -> str:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Default,{font_name},42,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,40,40,120,1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for segment in recipe.get("segments", []):
        caption = str(segment.get("caption", "")).strip()
        if not caption:
            continue
        lines.append(
            f"Dialogue: 0,{_format_ass_time(int(segment['start_ms']))},{_format_ass_time(int(segment['end_ms']))},Default,,0,0,0,,{_escape_ass(caption)}"
        )
    return "\n".join(lines) + "\n"


def write_ass(recipe: dict, output_path: Path, *, font_name: str = "Microsoft YaHei") -> None:
    target = recipe.get("target", {})
    width = int(target.get("width", 1080))
    height = int(target.get("height", 1920))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ass_from_recipe(recipe, width=width, height=height, font_name=font_name), encoding="utf-8")
```

- [ ] **Step 4: Write failing render-plan tests**

```python
# tests/test_render.py
def test_render_command_uses_voiceover_audio_instead_of_silent_track(tmp_path: Path):
    recipe, matches = _recipe(Path("assets/hook.mp4"))
    recipe["audio_strategy"] = "voiceover-only"
    recipe["voiceover_path"] = str(tmp_path / "voiceover.wav")
    recipe["caption_burn_in"] = True
    voiceover = tmp_path / "voiceover.wav"
    voiceover.write_bytes(b"RIFFfake")

    command = build_ffmpeg_plan(
        recipe,
        matches,
        _manifest("assets/hook.mp4"),
        Path("out/remix.mp4"),
        work_dir=Path("out"),
        reference_path=Path("reference.mp4"),
        asset_root=Path("assets"),
        captions_path=Path("out/captions.ass"),
        voiceover_path=voiceover,
    )

    assert "anullsrc" not in command
    assert str(voiceover) in command
    assert any("subtitles=" in part for part in command)
```

- [ ] **Step 5: Run render-plan test to verify it fails**

Run: `python -m pytest tests/test_render.py::test_render_command_uses_voiceover_audio_instead_of_silent_track -q`

Expected: fail because `voiceover_path` is not accepted and caption burn-in is not implemented.

- [ ] **Step 6: Implement render-plan changes**

```python
# src/jianji_flow/render.py signature changes
def build_ffmpeg_plan(..., captions_path: Path | None = None, voiceover_path: Path | None = None) -> list[str]:
    ...
    if captions_path is not None:
        reject_url_or_protocol(str(captions_path))
    if voiceover_path is not None:
        reject_url_or_protocol(str(voiceover_path))
    ...
    if captions_path is not None:
        escaped = captions_path.as_posix().replace(":", "\\:").replace("'", "\\'")
        video_filter += f",subtitles='{escaped}'"
    ...
    if recipe.get("audio_strategy") == "voiceover-only":
        command.extend(["-i", str(voiceover_path or recipe["voiceover_path"])])
        command.extend(["-map", "[vout]", "-map", f"{len(selected)}:a:0"])
    else:
        command.extend(["-f", "lavfi", "-t", f"{total_duration_s:.3f}", "-i", "anullsrc=channel_layout=mono:sample_rate=48000"])
        command.extend(["-map", "[vout]", "-map", f"{len(selected)}:a:0"])
```

- [ ] **Step 7: Run task tests**

Run: `python -m pytest tests/test_subtitles.py tests/test_render.py -q`

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add src/jianji_flow/subtitles.py src/jianji_flow/render.py tests/test_subtitles.py tests/test_render.py
git commit -m "Render voiceover and burned captions"
```

---

### Task 3: Contact Sheet And Review HTML

**Files:**
- Create: `src/jianji_flow/contact_sheet.py`
- Modify: `src/jianji_flow/review.py`
- Test: `tests/test_review.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: rendered `remix.mp4`, recipe, matches, review dictionary.
- Produces: `write_contact_sheet(video_path: Path, output_path: Path, *, frames: int = 5) -> Path`
- Produces: `build_review_html(review: dict, recipe: dict, matches: dict) -> str`
- Produces: `write_review_html(review: dict, recipe: dict, matches: dict, output_path: Path) -> None`

- [ ] **Step 1: Write failing review HTML tests**

```python
# tests/test_review.py
from jianji_flow.review import build_review_html, write_review_html


def test_build_review_html_contains_outputs_and_match_evidence():
    review = {
        "status": "pass",
        "outputs": {
            "remix": "work/remix.mp4",
            "contact_sheet": "work/contact-sheet.png",
            "voiceover": "work/voiceover.wav",
        },
        "warnings": [],
        "failures": [],
    }
    recipe = {"segments": [{"id": "seg-001", "match_id": "match-001", "caption": "家里难刷角落", "start_ms": 0, "end_ms": 1000}]}
    matches = {"matches": [{"id": "match-001", "asset_id": "asset-001", "source_path": "assets/hook.mp4", "confidence": 0.92, "evidence": ["filename-role:hook"]}]}

    html = build_review_html(review, recipe, matches)

    assert "<video" in html
    assert "work/remix.mp4" in html
    assert "work/contact-sheet.png" in html
    assert "家里难刷角落" in html
    assert "filename-role:hook" in html


def test_write_review_html_creates_file(tmp_path: Path):
    output = tmp_path / "review.html"

    write_review_html({"status": "pass", "outputs": {}}, {"segments": []}, {"matches": []}, output)

    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_review.py::test_build_review_html_contains_outputs_and_match_evidence tests/test_review.py::test_write_review_html_creates_file -q`

Expected: fail because HTML helpers are missing.

- [ ] **Step 3: Implement review HTML helpers**

```python
# src/jianji_flow/review.py additions
from html import escape


def build_review_html(review: dict, recipe: dict, matches: dict) -> str:
    outputs = review.get("outputs", {})
    match_by_id = _match_by_id(matches)
    rows = []
    for segment in recipe.get("segments", []):
        match = match_by_id.get(segment.get("match_id"), {})
        rows.append(
            "<tr>"
            f"<td>{escape(str(segment.get('id', '')))}</td>"
            f"<td>{escape(str(segment.get('start_ms', '')))}-{escape(str(segment.get('end_ms', '')))}</td>"
            f"<td>{escape(str(segment.get('caption', '')))}</td>"
            f"<td>{escape(str(match.get('source_path', '')))}</td>"
            f"<td>{escape(str(match.get('confidence', '')))}</td>"
            f"<td>{escape(', '.join(map(str, match.get('evidence', []))))}</td>"
            "</tr>"
        )
    return """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>jianji-flow review</title></head>
<body>
""" + f"""
<h1>jianji-flow Review: {escape(str(review.get('status', 'unknown')))}</h1>
<video controls src="{escape(str(outputs.get('remix', '')))}"></video>
<img alt="contact sheet" src="{escape(str(outputs.get('contact_sheet', '')))}">
<p>Voiceover: {escape(str(outputs.get('voiceover', '')))}</p>
<table><thead><tr><th>Segment</th><th>Time</th><th>Caption</th><th>Asset</th><th>Confidence</th><th>Evidence</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table>
</body></html>
"""


def write_review_html(review: dict, recipe: dict, matches: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_review_html(review, recipe, matches), encoding="utf-8")
```

- [ ] **Step 4: Write failing contact sheet tests**

```python
# tests/test_cli.py or tests/test_contact_sheet.py
from jianji_flow.contact_sheet import build_frame_times_ms


def test_build_frame_times_ms_spreads_frames_across_duration():
    assert build_frame_times_ms(10_000, frames=5) == [1000, 3000, 5000, 7000, 9000]
```

- [ ] **Step 5: Implement contact sheet helper**

```python
# src/jianji_flow/contact_sheet.py
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def build_frame_times_ms(duration_ms: int, *, frames: int = 5) -> list[int]:
    if duration_ms <= 0:
        raise ValueError("duration_ms must be positive")
    return [round(duration_ms * (index + 0.5) / frames) for index in range(frames)]


def write_contact_sheet(video_path: Path, output_path: Path, *, frames: int = 5) -> Path:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{max(frames, 1)},scale=220:-1,tile={frames}x1:padding=8:margin=8:color=white",
        "-frames:v",
        "1",
        str(output_path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "contact sheet generation failed")
    return output_path
```

- [ ] **Step 6: Run task tests**

Run: `python -m pytest tests/test_review.py tests/test_cli.py -q`

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/jianji_flow/contact_sheet.py src/jianji_flow/review.py tests/test_review.py tests/test_cli.py
git commit -m "Add review page artifacts"
```

---

### Task 4: CLI Wiring, Smoke Validation, Docs

**Files:**
- Modify: `src/jianji_flow/cli.py`
- Modify: `scripts/run_smoke.py`
- Modify: `scripts/run_p0.py`
- Modify: `README.md`
- Modify: `SKILL.md`
- Test: `tests/test_cli.py`
- Test: `tests/test_regression_outputs.py`

**Interfaces:**
- Consumes all helpers from Tasks 1-3.
- Produces default v0.2 outputs in the work directory: `voiceover.wav`, `captions.srt`, `captions.ass`, `remix.mp4`, `contact-sheet.png`, `review.md`, `review.html`.

- [ ] **Step 1: Write failing CLI output test**

```python
# tests/test_cli.py
def test_run_product_fixture_creates_v0_2_experience_outputs(tmp_path):
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    work_dir = tmp_path / "work"

    code = main([
        "run",
        "--mode",
        "product",
        "--reference",
        str(fixture_root / "scenario-a-product" / "reference.mp4"),
        "--assets",
        str(fixture_root / "scenario-a-product" / "assets"),
        "--script",
        str(fixture_root / "scenario-a-product" / "script.txt"),
        "--work-dir",
        str(work_dir),
        "--target-width",
        "320",
        "--target-height",
        "180",
        "--target-fps",
        "12",
    ])

    assert code == 0
    for name in ("voiceover.wav", "captions.srt", "captions.ass", "remix.mp4", "contact-sheet.png", "review.md", "review.html"):
        assert (work_dir / name).exists(), name
    assert run_ffprobe(work_dir / "remix.mp4").has_audio is True
    assert "<video" in (work_dir / "review.html").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run CLI output test to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_run_product_fixture_creates_v0_2_experience_outputs -q`

Expected: fail because v0.2 artifacts are not wired into the run.

- [ ] **Step 3: Wire v0.2 artifacts through CLI**

```python
# src/jianji_flow/cli.py imports
from jianji_flow.contact_sheet import write_contact_sheet
from jianji_flow.review import build_review, write_review_html, write_review_markdown
from jianji_flow.subtitles import write_ass, write_srt
from jianji_flow.voiceover import create_voiceover

# src/jianji_flow/cli.py paths after captions_path
ass_path = work_dir / "captions.ass"
voiceover_path = work_dir / "voiceover.wav"
contact_sheet_path = work_dir / "contact-sheet.png"
review_html_path = work_dir / "review.html"

# Build recipe with v0.2 fields
recipe = build_recipe(
    args.mode,
    target,
    segments,
    matches,
    output_path=work_dir / "remix.mp4",
    audio_strategy="voiceover-only",
    voiceover_path=voiceover_path,
    caption_burn_in=True,
)

# After validation
write_srt(recipe, captions_path)
write_ass(recipe, ass_path)
create_voiceover(recipe, voiceover_path)
render_preview(..., captions_path=ass_path, voiceover_path=voiceover_path)
write_contact_sheet(remix_path, contact_sheet_path)
review = build_review(recipe, matches, remix_path, captions_path, voiceover_path=voiceover_path, contact_sheet_path=contact_sheet_path, review_html_path=review_html_path)
write_review_markdown(review, review_path)
write_review_html(review, recipe, matches, review_html_path)
```

- [ ] **Step 4: Update smoke scripts**

```python
# scripts/run_smoke.py _assert_outputs
for name in ("manifest.json", "recipe.json", "matches.json", "captions.srt", "captions.ass", "voiceover.wav", "remix.mp4", "contact-sheet.png", "review.md", "review.html"):
    ...
```

- [ ] **Step 5: Update docs**

```markdown
## v0.2 can do
- Generate `voiceover.wav`.
- Burn captions into `remix.mp4`.
- Generate `review.html` and `contact-sheet.png`.

## v0.2 still does not do
- It does not create Jianying or CapCut drafts.
- It does not preserve source audio by default.
- It does not guarantee semantic matching beyond the current auditable matching evidence.
```

- [ ] **Step 6: Run full validation**

Run:

```powershell
python -m pytest -q
python scripts/run_smoke.py
python scripts/run_p0.py
python path\to\quick_validate.py path\to\jianji-flow
```

Expected:

- `pytest` passes.
- smoke passes.
- p0 passes.
- skill validation passes.

- [ ] **Step 7: Generate and inspect the home-product sample**

Run the same home-product command against:

- reference: `E:\jianji-sucai\b7415a57657864ddd62f6c44e33cdb6d.mp4`
- assets: `E:\AI-Companion\jianji-flow\out\home-product-test\generated-assets`
- script: `E:\AI-Companion\jianji-flow\out\home-product-test\home_product_script.txt`
- work dir: `E:\AI-Companion\jianji-flow\out\home-product-test\v0.2-run`

Inspect:

- `remix.mp4` plays.
- `remix.mp4` has audio.
- extracted frames show visible captions.
- `review.html` references the MP4, contact sheet, voiceover, and match evidence.

- [ ] **Step 8: Commit**

```bash
git add src/jianji_flow/cli.py scripts/run_smoke.py scripts/run_p0.py README.md SKILL.md tests/test_cli.py tests/test_regression_outputs.py
git commit -m "Wire v0.2 experience workflow"
```

---

## Self-Review

- Spec coverage: voiceover is covered by Task 1 and Task 4; caption burn-in by Task 2 and Task 4; review page and contact sheet by Task 3 and Task 4; docs and smoke validation by Task 4.
- Placeholder scan: passed; every task names concrete files, commands, and checks.
- Type consistency: `voiceover_path`, `caption_burn_in`, `captions_path`, `review.html`, and `contact-sheet.png` names are consistent across tasks.
