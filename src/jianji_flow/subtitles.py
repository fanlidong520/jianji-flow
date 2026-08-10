from __future__ import annotations

from pathlib import Path


def format_srt_time(ms: int) -> str:
    if ms < 0:
        raise ValueError("SRT time cannot be negative")

    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


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
