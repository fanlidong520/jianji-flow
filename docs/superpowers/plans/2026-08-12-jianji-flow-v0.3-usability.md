# jianji-flow v0.3 Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a narrow v0.3 usability layer so a new user can diagnose setup, run a demo, run a home-product quick draft, and understand what to fix next.

**Architecture:** Keep the existing v0.2 render pipeline as the engine. Add focused modules for environment diagnosis, asset diagnosis, quick-start defaults, and review summaries, then wire them into new CLI commands without breaking the existing `run` command.

**Tech Stack:** Python 3.10+, pytest, FFmpeg/ffprobe, Pillow, Windows local TTS through the existing voiceover module.

## Global Constraints

- Do not add Jianying or CapCut draft export in v0.3.
- Do not add a desktop editor UI.
- Do not search online for assets.
- Do not generate product footage.
- Do not add voice cloning, music, sound effects, or beat-sync editing.
- Do not claim output is ready to publish without human review.
- Keep `run` command behavior compatible with v0.2.
- Add tests before implementation for every behavior change.
- Keep user-facing failure messages short and actionable.
- Do not publish a v0.3 release until ten usability validation runs are recorded.

---

## File Structure

- Create `src/jianji_flow/environment.py`: environment readiness checks for Python, FFmpeg, ffprobe, TTS, and output writability.
- Create `src/jianji_flow/asset_diagnosis.py`: product role coverage and material readiness diagnosis.
- Create `src/jianji_flow/quickstart.py`: default quick command values and fallback product script.
- Create `src/jianji_flow/review_summary.py`: plain-language decision and next-action mapping.
- Modify `src/jianji_flow/cli.py`: add `doctor`, `demo`, and `quick` commands.
- Modify `src/jianji_flow/review.py`: include review summary in Markdown and HTML.
- Modify `scripts/check_env.py`: use environment diagnosis so CLI and script agree.
- Modify `README.md`, `SKILL.md`, `CHANGELOG.md`: document v0.3 commands and limits.
- Create `docs/validation/v0.3-usability-runs.md`: record ten validation runs before release.
- Add tests:
  - `tests/test_environment.py`
  - `tests/test_asset_diagnosis.py`
  - `tests/test_quickstart.py`
  - `tests/test_review_summary.py`
  - update `tests/test_cli.py`
  - update `tests/test_review.py`
  - update `tests/test_skill_metadata.py`

---

### Task 1: Environment Diagnosis And `doctor` Global Checks

**Files:**
- Create: `src/jianji_flow/environment.py`
- Modify: `scripts/check_env.py`
- Modify: `src/jianji_flow/cli.py`
- Test: `tests/test_environment.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `check_environment(output_root: Path | None = None) -> dict`
- Produces: `format_environment_report(report: dict) -> str`
- Produces: CLI command `jianji-flow doctor`

- [ ] **Step 1: Write failing environment tests**

Add to `tests/test_environment.py`:

```python
from pathlib import Path

from jianji_flow.environment import check_environment, format_environment_report


def test_check_environment_reports_core_tool_statuses(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "ffmpeg ok", "ffprobe": "ffprobe ok"},
    )
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: True)

    report = check_environment(output_root=tmp_path)

    assert report["status"] == "pass"
    assert report["checks"]["ffmpeg"]["status"] == "pass"
    assert report["checks"]["ffprobe"]["status"] == "pass"
    assert report["checks"]["local_tts"]["status"] == "pass"
    assert report["checks"]["writable_output"]["status"] == "pass"


def test_check_environment_reports_missing_tts_without_crashing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "ffmpeg ok", "ffprobe": "ffprobe ok"},
    )
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: False)

    report = check_environment(output_root=tmp_path)

    assert report["status"] == "fail"
    assert report["checks"]["local_tts"]["status"] == "fail"
    assert "Chinese TTS" in report["checks"]["local_tts"]["message"]


def test_format_environment_report_ends_with_plain_decision(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jianji_flow.environment.check_ffmpeg_available",
        lambda: {"ffmpeg": "ffmpeg ok", "ffprobe": "ffprobe ok"},
    )
    monkeypatch.setattr("jianji_flow.environment.has_local_chinese_tts", lambda: True)

    text = format_environment_report(check_environment(output_root=tmp_path))

    assert "Environment" in text
    assert text.strip().endswith("Ready to run quick draft")
```

- [ ] **Step 2: Run environment tests to verify they fail**

Run: `python -m pytest tests/test_environment.py -q`

Expected: fail with `ModuleNotFoundError` or missing functions.

- [ ] **Step 3: Implement minimal environment module**

Create `src/jianji_flow/environment.py`:

```python
from __future__ import annotations

import platform
import sys
import tempfile
from pathlib import Path

from jianji_flow.media_probe import check_ffmpeg_available
from jianji_flow.voiceover import has_local_chinese_tts


def _check(status: str, message: str) -> dict:
    return {"status": status, "message": message}


def _writable_output_check(output_root: Path | None) -> dict:
    root = output_root or Path(tempfile.gettempdir())
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".jianji-flow-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return _check("fail", f"Output directory is not writable: {exc}")
    return _check("pass", f"Output directory is writable: {root}")


def check_environment(output_root: Path | None = None) -> dict:
    tools = check_ffmpeg_available()
    checks = {
        "python": _check("pass", f"Python {sys.version.split()[0]} on {platform.system()}"),
        "ffmpeg": _check("pass" if tools.get("ffmpeg") else "fail", tools.get("ffmpeg") or "ffmpeg is missing"),
        "ffprobe": _check("pass" if tools.get("ffprobe") else "fail", tools.get("ffprobe") or "ffprobe is missing"),
        "local_tts": _check(
            "pass" if has_local_chinese_tts() else "fail",
            "Windows local Chinese TTS is available" if has_local_chinese_tts() else "Windows local Chinese TTS is not available",
        ),
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
    lines.append("")
    lines.append(decision)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Add TTS capability helper**

Modify `src/jianji_flow/voiceover.py`:

```python
def has_local_chinese_tts() -> bool:
    script = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voice = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
    if ($null -eq $voice) { exit 1 }
    exit 0
} finally {
    $s.Dispose()
}
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-EncodedCommand", _encoded_powershell(script)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0
```

Use this complete version so missing PowerShell returns `False` instead of
crashing:

```python
def has_local_chinese_tts() -> bool:
    script = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voice = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
    if ($null -eq $voice) { exit 1 }
    exit 0
} finally {
    $s.Dispose()
}
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", _encoded_powershell(script)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0
```

- [ ] **Step 5: Wire `doctor` command for environment-only report**

Modify `src/jianji_flow/cli.py` parser:

```python
doctor = commands.add_parser("doctor", help="check environment and optional materials")
doctor.add_argument("--reference")
doctor.add_argument("--assets")
doctor.add_argument("--script")
doctor.add_argument("--work-dir")
```

Add imports:

```python
from jianji_flow.environment import check_environment, format_environment_report
```

Add handler in `main()`:

```python
    if args.command == "doctor":
        output_root = Path(args.work_dir).resolve() if args.work_dir else None
        report = check_environment(output_root=output_root)
        print(format_environment_report(report), end="")
        return 0 if report["status"] == "pass" else 1
```

- [ ] **Step 6: Update `scripts/check_env.py` to share diagnosis**

Replace its body with:

```python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jianji_flow.environment import check_environment, format_environment_report


def main() -> int:
    report = check_environment()
    print(format_environment_report(report), end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Add CLI test for `doctor`**

Add to `tests/test_cli.py`:

```python
def test_doctor_prints_environment_report(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "jianji_flow.cli.check_environment",
        lambda output_root=None: {"status": "pass", "checks": {"python": {"status": "pass", "message": "Python ok"}}},
    )
    monkeypatch.setattr(
        "jianji_flow.cli.format_environment_report",
        lambda report: "# Environment\n- python: OK - Python ok\n\nReady to run quick draft\n",
    )

    code = main(["doctor", "--work-dir", str(tmp_path)])
    output = capsys.readouterr()

    assert code == 0
    assert "Ready to run quick draft" in output.out
```

- [ ] **Step 8: Run task tests**

Run: `python -m pytest tests/test_environment.py tests/test_cli.py -q`

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add src\jianji_flow\environment.py src\jianji_flow\voiceover.py src\jianji_flow\cli.py scripts\check_env.py tests\test_environment.py tests\test_cli.py
git commit -m "Add environment doctor"
```

---

### Task 2: Product Asset Diagnosis

**Files:**
- Create: `src/jianji_flow/asset_diagnosis.py`
- Test: `tests/test_asset_diagnosis.py`

**Interfaces:**
- Consumes: asset records from `scan_assets()`, product segment plan dictionaries.
- Produces: `diagnose_product_assets(assets: list[dict], segments: list[dict]) -> dict`
- Produces: `format_asset_diagnosis(report: dict) -> str`

- [ ] **Step 1: Write failing asset diagnosis tests**

Create `tests/test_asset_diagnosis.py`:

```python
from pathlib import Path

from jianji_flow.asset_diagnosis import diagnose_product_assets, format_asset_diagnosis
from jianji_flow.planner import build_segment_plan


def _asset(name: str, duration_ms: int = 10_000) -> dict:
    return {"asset_id": name, "path": Path(name).as_posix(), "duration_ms": duration_ms}


def test_product_asset_diagnosis_marks_well_named_roles_ready():
    segments = build_segment_plan("product", 10_000, None)
    assets = [_asset(f"01-{role}.mp4") for role in ("hook", "pain", "feature", "evidence", "cta")]

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "pass"
    assert all(item["status"] == "ready" for item in report["roles"].values())


def test_product_asset_diagnosis_marks_missing_role_as_fail():
    segments = build_segment_plan("product", 10_000, None)
    assets = [_asset("01-hook.mp4"), _asset("02-pain.mp4"), _asset("03-feature.mp4")]

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "fail"
    assert report["roles"]["evidence"]["status"] == "missing"
    assert any("Missing evidence clip" in item for item in report["actions"])


def test_product_asset_diagnosis_marks_short_role_as_weak():
    segments = build_segment_plan("product", 10_000, None)
    assets = [
        _asset("01-hook.mp4"),
        _asset("02-pain.mp4"),
        _asset("03-feature.mp4"),
        _asset("04-evidence.mp4", duration_ms=100),
        _asset("05-cta.mp4"),
    ]

    report = diagnose_product_assets(assets, segments)

    assert report["status"] == "warning"
    assert report["roles"]["evidence"]["status"] == "weak"
    assert "too short" in " ".join(report["actions"])


def test_format_asset_diagnosis_ends_with_decision():
    segments = build_segment_plan("product", 10_000, None)
    report = diagnose_product_assets([_asset(f"01-{role}.mp4") for role in ("hook", "pain", "feature", "evidence", "cta")], segments)

    text = format_asset_diagnosis(report)

    assert "Material diagnosis" in text
    assert text.strip().endswith("Ready to run quick draft")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_asset_diagnosis.py -q`

Expected: fail with missing module.

- [ ] **Step 3: Implement asset diagnosis**

Create `src/jianji_flow/asset_diagnosis.py`:

```python
from __future__ import annotations

from pathlib import Path


ROLE_HINTS = {
    "hook": ("hook", "opening", "result", "intro", "\u5f00\u5934", "\u6548\u679c"),
    "pain": ("pain", "problem", "dust", "dirty", "before", "\u75db\u70b9", "\u810f", "\u7070"),
    "feature": ("feature", "product", "brush", "detail", "\u5356\u70b9", "\u4ea7\u54c1", "\u5237"),
    "evidence": ("evidence", "demo", "use", "before-after", "after", "\u6f14\u793a", "\u4f7f\u7528", "\u5bf9\u6bd4"),
    "cta": ("cta", "ending", "packshot", "order", "buy", "\u7ed3\u5c3e", "\u4e0b\u5355", "\u8d2d\u4e70"),
}


def _asset_path(asset: dict) -> str:
    return str(asset.get("path", ""))


def _role_segment_duration(role: str, segments: list[dict]) -> int:
    for segment in segments:
        if segment.get("role") == role:
            return int(segment["end_ms"]) - int(segment["start_ms"])
    return 0


def _matches_role(role: str, asset: dict) -> bool:
    name = Path(_asset_path(asset)).stem.casefold()
    return any(hint.casefold() in name for hint in ROLE_HINTS[role])


def diagnose_product_assets(assets: list[dict], segments: list[dict]) -> dict:
    roles: dict[str, dict] = {}
    actions: list[str] = []
    if not assets:
        return {
            "status": "fail",
            "roles": {},
            "actions": ["No decodable video assets found. Add local .mp4 clips to the assets folder."],
        }

    for role in ROLE_HINTS:
        needed_ms = _role_segment_duration(role, segments)
        candidates = [asset for asset in assets if _matches_role(role, asset)]
        long_enough = [asset for asset in candidates if int(asset.get("duration_ms", 0)) >= needed_ms]
        if long_enough:
            roles[role] = {"status": "ready", "message": f"{role} clip is ready", "candidates": [_asset_path(item) for item in long_enough]}
        elif candidates:
            roles[role] = {"status": "weak", "message": f"{role} clip is too short", "candidates": [_asset_path(item) for item in candidates]}
            actions.append(f"Weak {role} clip: asset too short for the target segment.")
        else:
            roles[role] = {"status": "missing", "message": f"{role} clip is missing", "candidates": []}
            actions.append(f"Missing {role} clip: add a video for the {role} segment.")

    if any(item["status"] == "missing" for item in roles.values()):
        status = "fail"
    elif any(item["status"] == "weak" for item in roles.values()):
        status = "warning"
    else:
        status = "pass"
    return {"status": status, "roles": roles, "actions": actions}


def format_asset_diagnosis(report: dict) -> str:
    lines = ["# Material diagnosis"]
    for role, item in report.get("roles", {}).items():
        label = item.get("status", "unknown").upper()
        lines.append(f"- {role}: {label} - {item.get('message', '')}")
    actions = report.get("actions", [])
    if actions:
        lines.append("")
        lines.append("Next actions:")
        lines.extend(f"- {action}" for action in actions)
    decision = {
        "pass": "Ready to run quick draft",
        "warning": "Can run, but review carefully",
        "fail": "Not ready",
    }.get(report.get("status"), "Not ready")
    lines.append("")
    lines.append(decision)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run task tests**

Run: `python -m pytest tests/test_asset_diagnosis.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\jianji_flow\asset_diagnosis.py tests\test_asset_diagnosis.py
git commit -m "Add product asset diagnosis"
```

---

### Task 3: `demo` And `quick` Commands

**Files:**
- Create: `src/jianji_flow/quickstart.py`
- Modify: `src/jianji_flow/cli.py`
- Test: `tests/test_quickstart.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `default_product_script() -> str`
- Produces: `default_quick_work_dir(root: Path | None = None) -> Path`
- Produces: CLI command `jianji-flow demo`
- Produces: CLI command `jianji-flow quick --reference PATH --assets PATH [--script PATH] [--work-dir PATH]`

- [ ] **Step 1: Write failing quickstart tests**

Create `tests/test_quickstart.py`:

```python
from pathlib import Path

from jianji_flow.quickstart import default_product_script, default_quick_work_dir


def test_default_product_script_has_five_short_lines():
    lines = default_product_script().splitlines()

    assert len(lines) == 5
    assert all(line.strip() for line in lines)
    assert not any("\u4fdd\u8bc1" in line or "\u6700\u4f4e\u4ef7" in line for line in lines)


def test_default_quick_work_dir_uses_out_quick_prefix(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("jianji_flow.quickstart._timestamp", lambda: "20260812-010203")

    path = default_quick_work_dir(tmp_path)

    assert path == tmp_path / "out" / "quick-20260812-010203"
```

- [ ] **Step 2: Run quickstart tests to verify they fail**

Run: `python -m pytest tests/test_quickstart.py -q`

Expected: fail with missing module.

- [ ] **Step 3: Implement quickstart helpers**

Create `src/jianji_flow/quickstart.py`:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def default_product_script() -> str:
    return "\n".join(
        [
            "\u5bb6\u91cc\u8fd9\u4e9b\u96be\u6e05\u6d01\u7684\u89d2\u843d, \u4e00\u628a\u5de5\u5177\u5c31\u80fd\u7701\u4e0d\u5c11\u4e8b",
            "\u7a97\u7eb1\u79ef\u7070, \u5730\u7f1d\u53d1\u9ed1, \u666e\u901a\u62d6\u628a\u5f88\u96be\u5904\u7406\u5e72\u51c0",
            "\u8fd9\u4e2a\u53ef\u4f38\u7f29\u6e05\u6d01\u5237, \u786c\u6bdb\u5237\u5934\u80fd\u4f38\u8fdb\u7ec6\u7f1d",
            "\u5237\u7a97\u7eb1, \u5237\u5730\u7f1d, \u5237\u5899\u89d2, \u65e5\u5e38\u6e05\u6d01\u66f4\u987a\u624b",
            "\u5bb6\u91cc\u6709\u8fd9\u4e9b\u6e05\u6d01\u96be\u9898\u7684, \u53ef\u4ee5\u5907\u4e00\u628a\u8bd5\u8bd5",
        ]
    )


def default_quick_work_dir(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / "out" / f"quick-{_timestamp()}"
```

- [ ] **Step 4: Add CLI tests for `demo` and `quick` with patched voiceover**

Add to `tests/test_cli.py`:

```python
def test_demo_command_creates_sample_outputs(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)

    code = main(["demo", "--work-dir", str(tmp_path / "demo")])

    assert code == 0
    assert (tmp_path / "demo" / "remix.mp4").exists()
    assert (tmp_path / "demo" / "review.html").exists()
    assert (tmp_path / "demo" / "contact-sheet.png").exists()


def test_quick_uses_default_product_script_when_script_missing(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    work_dir = tmp_path / "quick"

    code = main(
        [
            "quick",
            "--reference",
            str(fixture_root / "scenario-a-product" / "reference.mp4"),
            "--assets",
            str(fixture_root / "scenario-a-product" / "assets"),
            "--work-dir",
            str(work_dir),
            "--target-width",
            "320",
            "--target-height",
            "180",
            "--target-fps",
            "12",
        ]
    )

    assert code == 0
    recipe_text = (work_dir / "recipe.json").read_text(encoding="utf-8")
    assert "No script was provided" not in recipe_text
    assert "家里这些难清洁" in recipe_text
    assert (work_dir / "review.html").exists()
```

- [ ] **Step 5: Run CLI tests to verify they fail**

Run: `python -m pytest tests/test_quickstart.py tests/test_cli.py::test_demo_command_creates_sample_outputs tests/test_cli.py::test_quick_uses_default_product_script_when_script_missing -q`

Expected: fail because commands are missing.

- [ ] **Step 6: Wire `demo` parser**

Modify `src/jianji_flow/cli.py` parser:

```python
demo = commands.add_parser("demo", help="generate a sample product draft")
demo.add_argument("--work-dir")
demo.add_argument("--target-width", type=int, default=320)
demo.add_argument("--target-height", type=int, default=180)
demo.add_argument("--target-fps", type=float, default=12)
```

Import fixture generation:

```python
from scripts.generate_fixtures import generate_fixtures
```

If importing from `scripts` is not reliable, move `generate_fixtures` reusable logic into `src/jianji_flow/fixtures.py` and keep `scripts/generate_fixtures.py` as a thin wrapper.

- [ ] **Step 7: Wire `quick` parser**

Modify parser:

```python
quick = commands.add_parser("quick", help="run the shortest home-product draft flow")
quick.add_argument("--reference", required=True)
quick.add_argument("--assets", required=True)
quick.add_argument("--script")
quick.add_argument("--work-dir")
quick.add_argument("--mode", choices=("product", "talking-head"), default="product")
quick.add_argument("--target-width", type=int)
quick.add_argument("--target-height", type=int)
quick.add_argument("--target-fps", type=float)
quick.add_argument("--confidence-threshold", type=float)
```

- [ ] **Step 8: Refactor `_run_pipeline` to accept script text override**

Modify signature:

```python
def _run_pipeline(args: argparse.Namespace, *, script_text_override: str | None = None) -> int:
```

Replace:

```python
script_text = _read_script(args.script)
```

with:

```python
script_text = script_text_override if script_text_override is not None else _read_script(args.script)
```

- [ ] **Step 9: Implement command handlers**

In `main()`:

```python
    if args.command == "demo":
        work_dir = Path(args.work_dir).resolve() if args.work_dir else default_quick_work_dir(Path.cwd())
        fixture_root = work_dir.parent / f"{work_dir.name}-fixtures"
        generate_fixtures(fixture_root)
        demo_args = argparse.Namespace(
            command="run",
            mode="product",
            reference=str(fixture_root / "scenario-a-product" / "reference.mp4"),
            assets=str(fixture_root / "scenario-a-product" / "assets"),
            script=str(fixture_root / "scenario-a-product" / "script.txt"),
            work_dir=str(work_dir),
            confidence_threshold=None,
            target_width=args.target_width,
            target_height=args.target_height,
            target_fps=args.target_fps,
        )
        return _run_pipeline(demo_args)
    if args.command == "quick":
        if not args.work_dir:
            args.work_dir = str(default_quick_work_dir(Path.cwd()))
        script_override = None if args.script else default_product_script()
        return _run_pipeline(args, script_text_override=script_override)
```

Add imports:

```python
from jianji_flow.quickstart import default_product_script, default_quick_work_dir
```

- [ ] **Step 10: Run task tests**

Run: `python -m pytest tests/test_quickstart.py tests/test_cli.py -q`

Expected: pass.

- [ ] **Step 11: Commit**

```powershell
git add src\jianji_flow\quickstart.py src\jianji_flow\cli.py tests\test_quickstart.py tests\test_cli.py
git commit -m "Add demo and quick commands"
```

---

### Task 4: Material Gate For `quick`

**Files:**
- Modify: `src/jianji_flow/cli.py`
- Modify: `src/jianji_flow/asset_diagnosis.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_asset_diagnosis.py`

**Interfaces:**
- Consumes: `diagnose_product_assets()`
- Produces: `diagnosis.md` in work dir when `quick` stops before rendering.

- [ ] **Step 1: Add failing CLI test for missing-role quick stop**

Add to `tests/test_cli.py`:

```python
def test_quick_stops_before_render_when_product_roles_are_missing(tmp_path, monkeypatch):
    _patch_voiceover(monkeypatch)
    fixture_root = tmp_path / "fixtures"
    subprocess.run([sys.executable, str(GENERATOR), "--output", str(fixture_root)], check=True)
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    first_asset = next((fixture_root / "scenario-a-product" / "assets").glob("*.mp4"))
    shutil.copy(first_asset, incomplete / "01-hook.mp4")
    work_dir = tmp_path / "quick"

    code = main(
        [
            "quick",
            "--reference",
            str(fixture_root / "scenario-a-product" / "reference.mp4"),
            "--assets",
            str(incomplete),
            "--work-dir",
            str(work_dir),
            "--target-width",
            "320",
            "--target-height",
            "180",
            "--target-fps",
            "12",
        ]
    )

    assert code == 1
    assert (work_dir / "diagnosis.md").exists()
    assert "Missing" in (work_dir / "diagnosis.md").read_text(encoding="utf-8")
    assert not (work_dir / "remix.mp4").exists()
```

Ensure `shutil` is imported in `tests/test_cli.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_quick_stops_before_render_when_product_roles_are_missing -q`

Expected: fail because quick renders or no diagnosis file exists.

- [ ] **Step 3: Add diagnosis writer helper in `cli.py`**

Add imports:

```python
from jianji_flow.asset_diagnosis import diagnose_product_assets, format_asset_diagnosis
```

Add helper:

```python
def _write_diagnosis(work_dir: Path, text: str) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / "diagnosis.md"
    path.write_text(text, encoding="utf-8")
    return path
```

- [ ] **Step 4: Gate quick before rendering**

In `quick` handler, after `script_override` is decided and before calling
`_run_pipeline(args, script_text_override=script_override)`:

```python
        work_dir = make_output_dir(Path(args.work_dir).resolve().parent, Path(args.work_dir).name)
        reference_path = resolve_existing_file(args.reference)
        asset_root = resolve_existing_dir(args.assets)
        reference_info = run_ffprobe(reference_path)
        records = scan_assets(asset_root)
        segments = build_segment_plan(args.mode, reference_info.duration_ms, script_override)
        if args.mode == "product":
            report = diagnose_product_assets(
                [{"asset_id": item.id, "path": item.path.as_posix(), "duration_ms": item.duration_ms} for item in records],
                segments,
            )
            if report["status"] == "fail":
                diagnosis_path = _write_diagnosis(work_dir, format_asset_diagnosis(report))
                print(f"quick stopped; diagnosis written to {diagnosis_path}", file=sys.stderr)
                return 1
```

Important: preserve existing stale artifact cleanup behavior by calling `_clear_success_artifacts(work_dir)` before writing diagnosis.

- [ ] **Step 5: Run task tests**

Run: `python -m pytest tests/test_asset_diagnosis.py tests/test_cli.py -q`

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src\jianji_flow\cli.py src\jianji_flow\asset_diagnosis.py tests\test_cli.py tests\test_asset_diagnosis.py
git commit -m "Gate quick runs with material diagnosis"
```

---

### Task 5: Plain-Language Review Summary

**Files:**
- Create: `src/jianji_flow/review_summary.py`
- Modify: `src/jianji_flow/review.py`
- Test: `tests/test_review_summary.py`
- Test: `tests/test_review.py`

**Interfaces:**
- Produces: `build_review_summary(review: dict) -> dict`
- Review dictionaries gain optional `summary` with `decision`, `reason`, `next_action`.

- [ ] **Step 1: Write failing review summary tests**

Create `tests/test_review_summary.py`:

```python
from jianji_flow.review_summary import build_review_summary


def test_review_summary_maps_pass_to_usable_rough_cut():
    summary = build_review_summary({"status": "pass", "warnings": [], "failures": [], "low_confidence_segments": []})

    assert summary["decision"] == "Usable rough cut"
    assert "Watch captions" in summary["next_action"]


def test_review_summary_maps_warning_to_needs_review():
    summary = build_review_summary({"status": "warning", "warnings": ["seg-004 low confidence: 0.55"], "failures": [], "low_confidence_segments": ["seg-004"]})

    assert summary["decision"] == "Needs review"
    assert "low confidence" in summary["reason"]


def test_review_summary_maps_fail_to_do_not_use():
    summary = build_review_summary({"status": "fail", "warnings": [], "failures": ["seg-002 missing asset"], "missing_segments": ["seg-002"]})

    assert summary["decision"] == "Do not use yet"
    assert "missing" in summary["reason"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_review_summary.py -q`

Expected: missing module.

- [ ] **Step 3: Implement `review_summary.py`**

Create:

```python
from __future__ import annotations


def build_review_summary(review: dict) -> dict:
    status = review.get("status")
    failures = list(review.get("failures", []))
    warnings = list(review.get("warnings", []))
    if status == "pass":
        return {
            "decision": "Usable rough cut",
            "reason": "All required artifacts passed automated checks.",
            "next_action": "Watch captions, product accuracy, and segment choices before publishing.",
        }
    if status == "warning":
        reason = warnings[0] if warnings else "Some segments need manual review."
        return {
            "decision": "Needs review",
            "reason": reason,
            "next_action": "Open the contact sheet and check low confidence segments before using the video.",
        }
    reason = failures[0] if failures else "The run did not pass required checks."
    return {
        "decision": "Do not use yet",
        "reason": reason,
        "next_action": "Fix the reported material or setup problem, then rerun quick.",
    }
```

- [ ] **Step 4: Attach summary in `build_review`**

Modify `src/jianji_flow/review.py`:

```python
from jianji_flow.review_summary import build_review_summary
```

Before return:

```python
    review["summary"] = build_review_summary(review)
```

- [ ] **Step 5: Show summary in Markdown**

Modify `build_review_markdown()` after status:

```python
        "",
        "## Summary",
        f"- Decision: {summary.get('decision', 'Unknown')}",
        f"- Reason: {summary.get('reason', '')}",
        f"- Next action: {summary.get('next_action', '')}",
```

Define:

```python
    summary = review.get("summary", build_review_summary(review))
```

- [ ] **Step 6: Show summary in HTML**

Modify `build_review_html()` after `<h1>`:

```python
  <section>
    <h2>Summary</h2>
    <p><strong>Decision:</strong> {escape(str(summary.get('decision', 'Unknown')))}</p>
    <p><strong>Reason:</strong> {escape(str(summary.get('reason', '')))}</p>
    <p><strong>Next action:</strong> {escape(str(summary.get('next_action', '')))}</p>
  </section>
```

Define:

```python
    summary = review.get("summary", build_review_summary(review))
```

- [ ] **Step 7: Add review tests**

Add to `tests/test_review.py`:

```python
def test_build_review_markdown_contains_plain_language_summary():
    markdown = build_review_markdown({"status": "pass", "outputs": {}, "warnings": [], "failures": []})

    assert "## Summary" in markdown
    assert "Usable rough cut" in markdown
    assert "Next action" in markdown


def test_build_review_html_contains_plain_language_summary():
    html = build_review_html({"status": "warning", "outputs": {}, "warnings": ["low confidence"], "failures": []}, {"segments": []}, {"matches": []})

    assert "<h2>Summary</h2>" in html
    assert "Needs review" in html
```

- [ ] **Step 8: Run task tests**

Run: `python -m pytest tests/test_review_summary.py tests/test_review.py -q`

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add src\jianji_flow\review_summary.py src\jianji_flow\review.py tests\test_review_summary.py tests\test_review.py
git commit -m "Add plain language review summary"
```

---

### Task 6: Documentation, Metadata, And Usability Validation Record

**Files:**
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_skill_metadata.py`
- Create: `docs/validation/v0.3-usability-runs.md`

**Interfaces:**
- Documents `doctor`, `demo`, and `quick`.
- Records ten usability validation runs before v0.3 release.

- [ ] **Step 1: Write failing metadata tests**

Add to `tests/test_skill_metadata.py`:

```python
def test_readme_documents_v0_3_usability_commands():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "jianji-flow doctor" in text
    assert "jianji-flow demo" in text
    assert "jianji-flow quick" in text
    assert "Ready to run quick draft" in text


def test_skill_documents_quick_start_commands():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "doctor" in text
    assert "demo" in text
    assert "quick" in text
    assert "diagnosis.md" in text


def test_v0_3_validation_record_has_ten_runs():
    text = (ROOT / "docs" / "validation" / "v0.3-usability-runs.md").read_text(encoding="utf-8")
    assert text.count("## Run ") == 10
    assert "usable rough cut" in text
    assert "do not use yet" in text
```

- [ ] **Step 2: Run metadata tests to verify they fail**

Run: `python -m pytest tests/test_skill_metadata.py -q`

Expected: fail because docs are missing v0.3 commands and validation record.

- [ ] **Step 3: Update README**

Add a v0.3 quick start section:

```markdown
## v0.3 Quick Start

Check your machine:

```powershell
jianji-flow doctor
```

See a sample without preparing materials:

```powershell
jianji-flow demo
```

Run a home-product draft with your own clips:

```powershell
jianji-flow quick --reference examples\reference.mp4 --assets examples\assets
```

`quick` stops with `diagnosis.md` when required materials are missing. A healthy
run ends with `Ready to run quick draft`, `review.html`, `contact-sheet.png`,
and `remix.mp4`.
```

- [ ] **Step 4: Update SKILL.md**

Add to workflow:

```markdown
For first-time users, prefer:

1. `jianji-flow doctor`
2. `jianji-flow demo`
3. `jianji-flow quick --reference examples\reference.mp4 --assets examples\assets`

If `quick` writes `diagnosis.md`, report the missing or weak material roles and
do not describe the run as a completed video.
```

- [ ] **Step 5: Update CHANGELOG**

Add unreleased section:

```markdown
## Unreleased

- Planned v0.3 usability layer: `doctor`, `demo`, `quick`, material diagnosis,
  and plain-language review summary.
```

- [ ] **Step 6: Create validation record template and fill ten runs after implementation**

Create `docs/validation/v0.3-usability-runs.md`:

```markdown
# v0.3 Usability Validation Runs

## Run 1

- Type: synthetic fixture
- Command: `jianji-flow demo --work-dir out/validation/run-01`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation

## Run 2

- Type: synthetic fixture
- Command: `jianji-flow demo --work-dir out/validation/run-02`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation

## Run 3

- Type: synthetic fixture
- Command: `jianji-flow demo --work-dir out/validation/run-03`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation

## Run 4

- Type: clear home-product filenames
- Command: `jianji-flow quick --reference out/validation/reference.mp4 --assets out/validation/assets-clear-01 --work-dir out/validation/run-04`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation

## Run 5

- Type: clear home-product filenames
- Command: `jianji-flow quick --reference out/validation/reference.mp4 --assets out/validation/assets-clear-02 --work-dir out/validation/run-05`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation

## Run 6

- Type: clear home-product filenames
- Command: `jianji-flow quick --reference out/validation/reference.mp4 --assets out/validation/assets-clear-03 --work-dir out/validation/run-06`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation

## Run 7

- Type: weak or messy filenames
- Command: `jianji-flow quick --reference out/validation/reference.mp4 --assets out/validation/assets-messy-01 --work-dir out/validation/run-07`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation

## Run 8

- Type: weak or messy filenames
- Command: `jianji-flow quick --reference out/validation/reference.mp4 --assets out/validation/assets-messy-02 --work-dir out/validation/run-08`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation

## Run 9

- Type: no-script quick run
- Command: `jianji-flow quick --reference out/validation/reference.mp4 --assets out/validation/assets-clear-01 --work-dir out/validation/run-09`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation

## Run 10

- Type: intentionally incomplete asset folder
- Command: `jianji-flow quick --reference out/validation/reference.mp4 --assets out/validation/assets-incomplete --work-dir out/validation/run-10`
- Outcome: not run yet
- User next action clear within 30 seconds: not evaluated
- Review page decision clear: not evaluated
- Remaining issue: pending implementation
```

Fill all ten runs only after actually running them. Do not fake validation.

- [ ] **Step 7: Run full local validation**

Run:

```powershell
python -m pytest -q
python scripts/run_smoke.py
python scripts/run_p0.py
git diff --check
```

Expected:

- pytest passes.
- smoke passes.
- P0 passes.
- diff check is clean.

- [ ] **Step 8: Commit**

```powershell
git add README.md SKILL.md CHANGELOG.md tests\test_skill_metadata.py docs\validation\v0.3-usability-runs.md
git commit -m "Document v0.3 usability workflow"
```

- [ ] **Step 9: Push and verify GitHub CI**

Run:

```powershell
git push
gh run list --repo fanlidong520/jianji-flow --limit 3
gh run watch <latest-run-id> --repo fanlidong520/jianji-flow --exit-status
```

Expected: latest CI conclusion is success.

---

## Final Validation Checklist

- [ ] `jianji-flow doctor` gives a short environment decision.
- [ ] `jianji-flow demo` creates `remix.mp4`, `review.html`, and `contact-sheet.png`.
- [ ] `jianji-flow quick --reference examples\reference.mp4 --assets examples\assets` works with no script for sufficient product assets.
- [ ] `quick` writes `diagnosis.md` and stops before rendering when product roles are missing.
- [ ] `review.md` and `review.html` include decision, reason, and next action.
- [ ] Existing `run` command still works.
- [ ] Full pytest passes.
- [ ] Smoke runner passes on Windows.
- [ ] P0 runner passes on Windows.
- [ ] GitHub Actions CI passes.
- [ ] Ten usability validation runs are recorded honestly.

## Self-Review

- Spec coverage: covered `doctor`, `demo`, `quick`, material diagnosis, default script, review summary, docs, and ten-run validation.
- Placeholder scan: checked red-flag terms and removed incomplete examples, placeholder paths, and undefined command names.
- Type consistency: function names are consistent across tasks: `check_environment`, `diagnose_product_assets`, `default_product_script`, `build_review_summary`.
- Scope check: no editor UI, no Jianying draft export, no web asset search, no full semantic matching.
