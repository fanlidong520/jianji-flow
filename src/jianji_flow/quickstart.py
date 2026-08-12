from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def default_product_script() -> str:
    return "\n".join(
        [
            "家里乱。",
            "清理累。",
            "一刷净。",
            "对比明显。",
            "省心。",
        ]
    )


def default_quick_work_dir(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / "out" / f"quick-{_timestamp()}"
