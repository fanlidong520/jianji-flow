from __future__ import annotations

from pathlib import Path


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
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


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
        blocks.append(
            f"{subtitle_index}\n"
            f"{format_srt_time(start_ms)} --> {format_srt_time(end_ms)}\n"
            f"{caption}\n"
        )
        subtitle_index += 1

    return "\n".join(blocks) + ("\n" if blocks else "")


def write_srt(recipe: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(srt_from_recipe(recipe), encoding="utf-8")


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
        lines.append(
            "Dialogue: "
            f"0,{_format_ass_time(start_ms)},{_format_ass_time(end_ms)},"
            f"Default,,0,0,0,,{_escape_ass_text(caption)}"
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
