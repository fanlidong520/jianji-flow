from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def default_product_script() -> str:
    return "\n".join(
        [
            "家里难清理的地方，往往就藏在角落。",
            "纱窗、缝隙和锅底，普通抹布很难够到。",
            "一套工具分工清楚，不同位置用不同刷头。",
            "刷地、清缝、擦窗，看到哪里脏就处理哪里。",
            "想让家务省点力，顺手工具备几件就够了。",
        ]
    )


def default_quick_work_dir(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / "out" / f"quick-{_timestamp()}"
