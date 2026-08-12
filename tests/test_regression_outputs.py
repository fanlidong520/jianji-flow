import platform
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


pytestmark = pytest.mark.skipif(
    platform.system() != "Windows",
    reason="smoke and p0 runners require Windows local TTS",
)


def test_smoke_runner_completes():
    result = subprocess.run(
        [sys.executable, "scripts/run_smoke.py"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr


def test_p0_runner_completes():
    result = subprocess.run(
        [sys.executable, "scripts/run_p0.py"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
