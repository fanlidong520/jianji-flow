# Visual Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auditable Codex-assisted visual candidate and selection loop that works with opaque asset filenames.

**Architecture:** Generate deterministic candidate windows and sampled frames in a focused `visual_candidates.py` module. Store selections by candidate id, validate them against the saved manifest and current asset scan, then reuse the existing matcher override and review pipeline. Keep semantic judgment in the Codex visual review step and keep local image metrics explicitly non-semantic.

**Tech Stack:** Python 3.10+, Pillow, FFmpeg/ffprobe, jsonschema, pytest, existing jianji-flow CLI and review artifacts.

## Global Constraints

- The base package must not require a cloud API or a heavyweight vision model.
- Frame quality metrics are diagnostic only and must never be presented as semantic matching.
- All selected paths and source ranges must be validated before voiceover or rendering.
- Invalid or stale selection runs must remove stale success artifacts.
- Existing `run`, `quick`, smoke, P0, and schema behavior must remain compatible.
- Human review is still required before publishing, even when visual-review evidence exists.

---

### Task 1: Add the candidate and selection contracts

**Files:**
- Create: `schemas/visual-selection.schema.json`
- Create: `tests/test_visual_candidates.py`
- Modify: `src/jianji_flow/contracts.py`

**Interfaces:**
- `validate_visual_selection(data: dict) -> None`
- The selection schema accepts `version`, `candidate_manifest`, and one selection per segment with `candidate_id`, `reviewer`, and `reason`.

- [ ] **Step 1: Write failing schema tests**

```python
def test_visual_selection_requires_candidate_and_reason():
    with pytest.raises(ValidationError):
        validate_visual_selection({"version": "0.1", "candidate_manifest": "visual-candidates.json", "selections": {"seg-001": {}}})
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m pytest tests/test_visual_candidates.py -q`
Expected: FAIL because the validator and schema do not exist.

- [ ] **Step 3: Add the schema and validator**

The schema must reject unknown top-level and selection fields, require a
non-empty `candidate_id`, a non-empty `reviewer`, and a non-empty `reason`, and
allow only `human` or `codex-vision` reviewers.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `python -m pytest tests/test_visual_candidates.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add schemas/visual-selection.schema.json src/jianji_flow/contracts.py tests/test_visual_candidates.py
git commit -m "feat: add visual selection contract"
```

### Task 2: Generate deterministic visual candidates and a board

**Files:**
- Create: `src/jianji_flow/visual_candidates.py`
- Modify: `tests/test_visual_candidates.py`

**Interfaces:**
- `build_visual_candidate_manifest(segments, assets, work_dir) -> dict`
- `write_visual_candidate_artifacts(manifest, segments, work_dir) -> dict`

- [ ] **Step 1: Add failing tests for windows, frame records, and bounded output**

Test start/middle/end windows, duration filtering, deterministic ids, fake
frame extraction, frame hashes, unavailable candidates, and the generated PNG
board. Assert that a quality score is labeled non-semantic data.

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `python -m pytest tests/test_visual_candidates.py -q`
Expected: FAIL because the module functions do not exist.

- [ ] **Step 3: Implement the minimal candidate module**

Use the existing FFmpeg subprocess boundary and Pillow. Keep candidate count
bounded per segment, extract three frames inside each window, write deterministic
relative paths under `visual-candidates/`, and include source asset SHA-256 and
frame SHA-256 values.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `python -m pytest tests/test_visual_candidates.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/jianji_flow/visual_candidates.py tests/test_visual_candidates.py
git commit -m "feat: generate visual candidate boards"
```

### Task 3: Apply and validate visual selections

**Files:**
- Modify: `src/jianji_flow/visual_candidates.py`
- Modify: `src/jianji_flow/matcher.py`
- Modify: `tests/test_visual_candidates.py`
- Modify: `tests/test_matcher.py`

**Interfaces:**
- `load_visual_selection(path) -> dict`
- `apply_visual_selections(segments, matches, assets, selection, candidate_manifest) -> dict`

- [ ] **Step 1: Add failing tests for valid and invalid selection binding**

Cover valid path/range updates, `visual-review:<candidate_id>` evidence,
unknown ids, cross-segment ids, changed asset digest, too-short range, and
unavailable frame candidates.

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `python -m pytest tests/test_visual_candidates.py tests/test_matcher.py -q`
Expected: FAIL for the new selection cases.

- [ ] **Step 3: Implement strict selection application**

Resolve the candidate manifest relative to the selection file, compare candidate
asset id/path/sha/duration to the current scan, validate source bounds, and
apply the selected source range without using filename roles. Preserve existing
override evidence and add the visual-review evidence.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `python -m pytest tests/test_visual_candidates.py tests/test_matcher.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/jianji_flow/visual_candidates.py src/jianji_flow/matcher.py tests/test_visual_candidates.py tests/test_matcher.py
git commit -m "feat: apply validated visual selections"
```

### Task 4: Wire the CLI and review evidence

**Files:**
- Modify: `src/jianji_flow/cli.py`
- Modify: `src/jianji_flow/review.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_review.py`

**Interfaces:**
- Add `visual-review` command.
- Add `--visual-selections` to `run` and `quick`.

- [ ] **Step 1: Add failing CLI and review tests**

Test board-only command output, opaque filename quick stop with board paths,
valid visual-selection quick run, invalid selection before render, and review
copy that says “Codex visual review” while rejecting semantic-score language.

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `python -m pytest tests/test_cli.py tests/test_review.py -q`
Expected: FAIL for the new command and option.

- [ ] **Step 3: Wire the candidate board and selection into the existing run**

Generate the board in `visual-review` and in the `quick` failure path for
missing roles. Load and apply selections before semantic validation. Do not
allow filename diagnosis to block a valid visual selection. Add board and
selection paths to review outputs and preserve stale-artifact cleanup.

- [ ] **Step 4: Add plain-language review output**

Show selected candidate id, asset, source range, reviewer, reason, and frame
paths in Markdown and HTML. Explain that visual review is model-assisted
evidence, not a numeric guarantee.

- [ ] **Step 5: Run focused tests and verify they pass**

Run: `python -m pytest tests/test_cli.py tests/test_review.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/jianji_flow/cli.py src/jianji_flow/review.py tests/test_cli.py tests/test_review.py
git commit -m "feat: wire visual selection into quick runs"
```

### Task 5: Update the Codex workflow and documentation

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/product-quality-bar.md`
- Modify: `docs/validation/product-grade-validation.md`

**Interfaces:**
- Document `visual-review`, candidate inspection, selection file format, and
  the honest limits of Codex-assisted selection.

- [ ] **Step 1: Add documentation tests**

Extend metadata tests to require the visual-review command, output names, and
the phrases explaining that local metrics are not semantic proof.

- [ ] **Step 2: Update workflow documentation**

Describe the shortest path from opaque filenames to candidate board, Codex frame
inspection, validated selections, rerun, and review.html. Include a warning
example and do not promise automatic publishing.

- [ ] **Step 3: Run documentation tests**

Run: `python -m pytest tests/test_skill_metadata.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add SKILL.md README.md CHANGELOG.md docs/product-quality-bar.md docs/validation/product-grade-validation.md tests/test_skill_metadata.py
git commit -m "docs: explain visual selection workflow"
```

### Task 6: Repeat real-material validation and final audit

**Files:**
- Create ignored validation outputs under `out/visual-selection-v35/`
- Modify: `docs/validation/product-grade-validation.md`
- Modify: `docs/product-grade-findings.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] **Step 1: Run focused and full tests**

Run: `python -m pytest -q`, `python scripts/run_smoke.py`, and `python scripts/run_p0.py`.

- [ ] **Step 2: Run the opaque filename board and inspect it visually**

Use the real home-product pack copied to `IMG_001.mp4` style names. Inspect
`visual-candidate-sheet.png`, fill a selection file only from visible candidate
ids, and rerun with `--visual-selections`.

- [ ] **Step 3: Verify actual outputs**

Check that all five matches carry visual-review evidence, selected ranges are
inside the current assets, review.html embeds candidate frames, and the output
is visibly re-edited rather than only retimed voiceover. Keep the run at
`warning` if any source UI, story, caption, or other risk remains.

- [ ] **Step 4: Run the stale and dirty-material checks**

Change one asset after creating the selection file and verify the rerun fails
before rendering. Run a deliberately contaminated fixture and verify it is
blocked rather than reported as pass.

- [ ] **Step 5: Update validation records and inspect the diff**

Record commands, output paths, user-facing judgment, remaining limitations,
test counts, and the fact that the goal is not complete until the launch rule is
met. Run `git diff --check` and review every changed file.

- [ ] **Step 6: Commit and push the verified implementation**

```powershell
git add docs/product-grade-findings.md docs/validation/product-grade-validation.md progress.md task_plan.md
git commit -m "test: validate visual selection on opaque filenames"
git push origin codex/v0.3-usability
```
