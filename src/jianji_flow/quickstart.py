from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def default_product_script() -> str:
    return "\n".join(
        [
            "家里这个角落最容易显乱。",
            "普通工具用起来费力，还不容易清理干净。",
            "这个小工具一推一刷，缝隙和台面都能照顾到。",
            "看一下前后对比，细节会更明显。",
            "适合想把家务做得更省心的人。",
        ]
    )


def default_quick_work_dir(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / "out" / f"quick-{_timestamp()}"
