from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jianji_flow.media_probe import check_ffmpeg_available


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    availability = check_ffmpeg_available()
    for name in ("ffmpeg", "ffprobe"):
        print(f"{name}: {availability[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
