from __future__ import annotations

import platform
import sys
import tempfile
from pathlib import Path

from jianji_flow.media_probe import check_ffmpeg_available
from jianji_flow.voiceover import has_local_chinese_tts


def _check(status: str, message: str) -> dict:
    return {"status": status, "message": message}


def _tool_check(tools: dict[str, str], name: str) -> dict:
    value = tools.get(name)
    if value and value != "missing":
        return _check("pass", value)
    return _check("fail", f"{name} is missing")


def _writable_output_check(output_root: Path | None) -> dict:
    root = output_root or Path(tempfile.gettempdir())
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".jianji-flow-write-test-",
            dir=root,
            delete=True,
        ) as probe:
            probe.write("ok")
    except OSError as exc:
        return _check("fail", f"Output directory is not writable: {exc}")
    return _check("pass", f"Output directory is writable: {root}")


def check_environment(output_root: Path | None = None) -> dict:
    tools = check_ffmpeg_available()
    system = platform.system()
    has_tts = has_local_chinese_tts() if system == "Windows" else False
    tts_message = (
        "Windows local Chinese TTS is available"
        if has_tts
        else (
            "Windows local Chinese TTS requires Windows; current platform: " + system
            if system != "Windows"
            else "Windows local Chinese TTS is not available"
        )
    )
    checks = {
        "python": _check("pass", f"Python {sys.version.split()[0]} on {system}"),
        "ffmpeg": _tool_check(tools, "ffmpeg"),
        "ffprobe": _tool_check(tools, "ffprobe"),
        "local_tts": _check("pass" if has_tts else "fail", tts_message),
        "writable_output": _writable_output_check(output_root),
    }
    status = "pass" if all(item["status"] == "pass" for item in checks.values()) else "fail"
    return {"status": status, "checks": checks}


def format_environment_report(report: dict) -> str:
    lines = ["# Environment"]
    for name, check in report.get("checks", {}).items():
        mark = "OK" if check.get("status") == "pass" else "FAIL"
        lines.append(f"- {name}: {mark} - {check.get('message', '')}")
    decision = "Ready to run quick draft" if report.get("status") == "pass" else "Not ready"
    if decision == "Not ready":
        checks = report.get("checks", {})
        lines.append("")
        lines.append("Next steps:")
        if checks.get("ffmpeg", {}).get("status") == "fail" or checks.get("ffprobe", {}).get("status") == "fail":
            lines.append("- Install FFmpeg and ffprobe, for example: winget install Gyan.FFmpeg")
        if checks.get("local_tts", {}).get("status") == "fail":
            lines.append("- On Windows, install or enable a local zh-CN text-to-speech voice.")
        if checks.get("writable_output", {}).get("status") == "fail":
            lines.append("- Choose a writable output folder with --work-dir.")
        lines.append("- Run this command again after fixing the items above.")
    lines.append("")
    lines.append(decision)
    return "\n".join(lines) + "\n"
