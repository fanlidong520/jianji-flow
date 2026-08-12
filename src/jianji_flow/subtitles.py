from __future__ import annotations

from pathlib import Path


_MAX_CAPTION_LINE_CHARS = 14


def format_srt_time(ms: int) -> str:
    if ms < 0:
        raise ValueError("SRT time cannot be negative")

    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _format_ass_time(ms: int) -> str:
    if ms < 0:
        raise ValueError("ASS time cannot be negative")

    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    centiseconds = milliseconds // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _escape_ass_text(text: str) -> str:
    escaped = text.replace("\\N", "\u0000")
    escaped = escaped.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")
    return escaped.replace("\u0000", "\\N")


def _is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def _split_caption_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    current: list[str] = []
    for char in text:
        if char in "\r\n":
            if current:
                phrases.append("".join(current).strip())
                current = []
            continue
        current.append(char)
        if char in "，。！？；、,.!?;":
            phrases.append("".join(current).strip())
            current = []
    if current:
        phrases.append("".join(current).strip())
    return [phrase for phrase in phrases if phrase]


def _wrap_caption_line(text: str, max_chars: int = _MAX_CAPTION_LINE_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    lines: list[str] = []
    current = ""
    for char in text:
        if len(current) >= max_chars and _is_cjk(char):
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines


def split_caption_for_display(text: str, max_chars: int = _MAX_CAPTION_LINE_CHARS) -> list[str]:
    parts: list[str] = []
    for phrase in _split_caption_phrases(text.strip()):
        parts.extend(_wrap_caption_line(phrase, max_chars=max_chars))
    return parts


def _caption_cues(start_ms: int, end_ms: int, caption: str) -> list[tuple[int, int, str]]:
    lines = split_caption_for_display(caption)
    if not lines:
        return []

    duration = end_ms - start_ms
    base = duration // len(lines)
    remainder = duration % len(lines)
    cues: list[tuple[int, int, str]] = []
    cursor = start_ms
    for index, line in enumerate(lines):
        cue_duration = base + (1 if index < remainder else 0)
        cue_end = end_ms if index == len(lines) - 1 else cursor + cue_duration
        cues.append((cursor, cue_end, line))
        cursor = cue_end
    return cues


def srt_from_recipe(recipe: dict) -> str:
    blocks: list[str] = []
    previous_end = 0
    subtitle_index = 1
    for segment in recipe.get("segments", []):
        start_ms = int(segment["start_ms"])
        end_ms = int(segment["end_ms"])
        if start_ms < previous_end:
            raise ValueError("subtitle segments overlap")
        if end_ms <= start_ms:
            raise ValueError("subtitle segment end_ms must be greater than start_ms")
        previous_end = end_ms

        caption = str(segment.get("caption", "")).strip()
        if not caption:
            continue
        for cue_start_ms, cue_end_ms, cue_text in _caption_cues(start_ms, end_ms, caption):
            blocks.append(
                f"{subtitle_index}\n"
                f"{format_srt_time(cue_start_ms)} --> {format_srt_time(cue_end_ms)}\n"
                f"{cue_text}\n"
            )
            subtitle_index += 1

    return "\n".join(blocks) + ("\n" if blocks else "")


def write_srt(recipe: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(srt_from_recipe(recipe), encoding="utf-8")


def _ass_caption_margin_v(height: int) -> int:
    return max(120, min(320, round(height * 0.18)))


def ass_from_recipe(recipe: dict, *, width: int, height: int, font_name: str = "Microsoft YaHei") -> str:
    margin_v = _ass_caption_margin_v(height)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Default,{font_name},42,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,40,40,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    previous_end = 0
    for segment in recipe.get("segments", []):
        start_ms = int(segment["start_ms"])
        end_ms = int(segment["end_ms"])
        if start_ms < previous_end:
            raise ValueError("subtitle segments overlap")
        if end_ms <= start_ms:
            raise ValueError("subtitle segment end_ms must be greater than start_ms")
        previous_end = end_ms

        caption = str(segment.get("caption", "")).strip()
        if not caption:
            continue
        for cue_start_ms, cue_end_ms, cue_text in _caption_cues(start_ms, end_ms, caption):
            wrapped = "\\N".join(_wrap_caption_line(cue_text))
            lines.append(
                "Dialogue: "
                f"0,{_format_ass_time(cue_start_ms)},{_format_ass_time(cue_end_ms)},"
                f"Default,,0,0,0,,{_escape_ass_text(wrapped)}"
            )
    return "\n".join(lines) + "\n"


def write_ass(recipe: dict, output_path: Path, *, font_name: str = "Microsoft YaHei") -> None:
    target = recipe.get("target", {})
    width = int(target.get("width", 1080))
    height = int(target.get("height", 1920))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        ass_from_recipe(recipe, width=width, height=height, font_name=font_name),
        encoding="utf-8",
    )
