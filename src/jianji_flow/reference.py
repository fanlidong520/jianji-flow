from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceBeat:
    role: str
    start_ms: int
    end_ms: int
    caption: str
