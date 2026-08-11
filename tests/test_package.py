import subprocess
import sys
import os
from pathlib import Path

import jianji_flow


ROOT = Path(__file__).resolve().parents[1]


def test_version_constant():
    assert jianji_flow.__version__ == "0.2.0"


def test_python_module_version_entrypoint():
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else os.pathsep.join([src_path, existing])
    result = subprocess.run(
        [sys.executable, "-m", "jianji_flow", "--version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0
    assert "jianji-flow 0.2.0" in result.stdout


def test_python_module_help_entrypoint():
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else os.pathsep.join([src_path, existing])
    result = subprocess.run(
        [sys.executable, "-m", "jianji_flow"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0
    assert "run" in result.stdout
