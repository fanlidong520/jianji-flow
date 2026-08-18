from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent
PYTEST_TMP_BASE = PROJECT_ROOT / "out" / "pytest-tmp"


def make_repo_tmp_path(prefix: str = "tmp") -> Path:
    PYTEST_TMP_BASE.mkdir(parents=True, exist_ok=True)
    path = PYTEST_TMP_BASE / f"{prefix}-{uuid.uuid4().hex[:12]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


@pytest.fixture
def tmp_path() -> Path:
    path = make_repo_tmp_path("pytest")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
