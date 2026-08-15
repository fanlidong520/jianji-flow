# jianji-flow

`jianji-flow` 是一个正在打磨中的 Codex 自动剪辑 skill：输入参考视频、本地素材目录和可选文案，输出一条可人工复核的短视频粗剪预览。

当前版本更像一个“本地自动粗剪工作流底座”，不是完整替代剪映的桌面剪辑软件。它会生成机器配音、烧录字幕、可播放预览视频、分段复核图和本地复核页，也会在素材明显不够、源片段疑似有旧字幕/平台 UI、或匹配证据太弱时给出 warning/fail，而不是假装成片已经可发。

当前最准确的定位是：**本地素材角色匹配 + 脚本驱动的可复核粗剪**。参考视频只提供结构、尺寸、帧率等参考，不会被复制到输出，也不会被真正拆解成镜头语言、节奏、钩子或视觉风格。

## 效果预览

下面是一次家居带货样片生成后的 `contact-sheet.png`，每一格对应一个时间线片段，方便快速检查画面和字幕是否正常。

![Home product demo contact sheet](docs/assets/home-product-contact-sheet.png)

## 适合谁

- 想用 Codex 自动跑短视频粗剪的人。
- 想先验证“固定短视频结构 -> 本地素材匹配 -> 自动生成预览”的创作者。
- 想做带货、口播切片、素材复用流程，但仍愿意人工复核结果的人。

## What It Does Now

- Builds a structured timeline for `product` or `talking-head` videos.
- Scans local video assets and writes `manifest.json`.
- Writes `diagnosis.md` for product quick runs so material readiness and source-frame risks are visible before judging the cut.
- Matches timeline segments to assets and writes `matches.json`.
- Writes `fixes.template.json` so weak or low-confidence segments can be replaced one by one.
- Accepts `--fixes fixes.template.json` to pin a segment or role to a replacement asset, with the override recorded in `matches.json`.
- Writes the authoritative timeline to `recipe.json`.
- Runs source preflight checks on selected source frames before voiceover and rendering.
- Runs source preflight on the same cropped safe area that the renderer will expose, reducing warnings for platform chrome that is removed before export.
- Generates `captions.srt` and `captions.ass`.
- Generates `voiceover.wav` with a local Windows Chinese TTS voice when available.
- Renders `remix.mp4` with burned-in captions and voiceover audio.
- Uses crop and caption outline for visual cleanup without adding full-frame dark bands over the video.
- Writes `contact-sheet.png` with one frame per timeline segment.
- Writes `reference-comparison.png` with the same number of relative storyboard samples from the reference and the remix, so the visible edit can be checked without guessing.
- Supports opt-in `--multi-shot` scene-boundary splitting, so a long selected source window can become several short visual shots while keeping the parent caption and voiceover segment intact.
- Writes `shot-plan.json` when `--multi-shot` is used, with the final retimed source boundaries and explicit fallback warnings.
- Preserves a visually confirmed source window across voiceover retiming with a bounded, auditable `playback_rate`, instead of silently trimming the reviewed content.
- Writes `candidate-review.html` and `candidate-frames/` so weak segments can be compared against visible repair candidates.
- Supports a separate `visual-review` pass that generates opaque-filename candidate boards; Codex should inspect the frames and write the selection file for the user instead of asking the user to edit JSON.
- Writes `review.md` and `review.html` for manual inspection, including a change report after fixes are applied.
- Records selected visual candidates, frame evidence, and asset fingerprints in `review.md`, `review.html`, and `matches.json`.
- Shows `CANDIDATE` in `diagnosis.md` for filename/duration-ready clips, because that is not visual proof.
- Marks filename-only matching as `warning` because it does not prove visual understanding.
- Adds a `Story support` review section that warns when most story roles have no non-filename visual evidence.
- Checks same-role repair recommendations with sampled frames and downgrades replacement files that still look like the current segment.

## What It Does Not Do

- It does not create Jianying or CapCut draft projects.
- It does not build a full desktop editing application.
- It does not search online for assets.
- It does not publish videos.
- It does not preserve source audio by default.
- It does not generate music, effects, or beat-synced edits.
- It does not truly decompose a viral reference video into camera moves, hooks, or pacing yet.
- Its default path still uses one source window per story segment; `--multi-shot` is a bounded structural cut, not semantic reference decomposition.
- It does not silently claim that a visual candidate board is semantic understanding; visual selection is an explicit Codex-assisted review step and still needs human product-accuracy review.
- It does not guarantee semantic matching beyond the current auditable matching evidence.
- It does not treat file names as visual proof. Role-labeled files help assembly, but the picture still needs review.

## 安装

环境要求：

- Python 3.10+
- FFmpeg and ffprobe
- Windows local TTS for default Chinese voiceover generation

Clone 仓库后，在项目目录里安装：

```powershell
python -m pip install -e ".[dev]"
```

如果当前 `python` 没有 pip，但 Windows Python Launcher 可用，可以改用：

```powershell
py -m pip install -e ".[dev]"
```

如果你在 CMD、bash 或 GitHub Actions 里运行，也可以用：

```bash
python -m pip install -e .[dev]
```

检查本机环境：

```powershell
python scripts/check_env.py
```

安装后也可以使用更短的命令：

```powershell
jianji-flow doctor
```

健康输出会以 `Ready to run quick draft` 结尾。
首次安装建议先确认版本和内置 demo 都能运行：

```powershell
python -m jianji_flow --version
jianji-flow demo
```

`demo` 会在本地生成合成素材和可检查的 `remix.mp4`；它不需要你的真实素材，也不会联网寻找素材。

## v0.3 Quick Start

第一次使用建议按三步走：

```powershell
jianji-flow doctor
```

没有素材时，先跑一个本地合成示例：

```powershell
jianji-flow demo
```

有自己的家居带货素材后，用最短命令跑一条粗剪：

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets
```

上面这条命令需要先运行 `python scripts/generate_fixtures.py --output fixtures`，或者把路径换成你自己的参考视频和素材文件夹。

`quick` 在没有传 `--script` 时会使用一组家居清洁带货样例文案，包含开头、痛点、分工、演示和收尾五段。默认文案只适合清洁类家居样例；如果是收纳、厨房、床品、灯具等其他产品，请传入自己的 `--script`。产品模式每次都会写出 `diagnosis.md`，先说明素材只是通过文件名和时长初筛；素材明显不够时，它会先停下，不会硬剪出一条误导性的坏视频。

如果 `doctor` 显示 FFmpeg 或 ffprobe 缺失，Windows 上可以先尝试：

```powershell
winget install Gyan.FFmpeg
```

如果显示中文 TTS 不可用，需要在 Windows 里安装或启用本地中文语音。修好后重新运行 `jianji-flow doctor`。

## 素材怎么准备

你需要准备三类输入：

- `reference.mp4`: 一条你想参考节奏和结构的视频。它只用于分析，不会被复制进输出视频。
- `assets/`: 你自己的本地素材文件夹，里面放可用的 `.mp4` 素材。
- `script.txt`: 可选文案。产品带货建议按“开头、痛点、卖点、演示、行动提醒”写成 3 到 8 段短句。

如果多个文件只是复制后改了名字，`diagnosis.md` 会标记为 `DUPLICATE MEDIA`。对于尺寸相同、时长接近的重新编码文件，以及时长相差不超过约 3 倍、短片大多数采样帧能在长片中找到对应画面的文件，它会标记 `SIMILAR MEDIA`；这仍是保守的风险提示，不代表已经证明来自同一母片，仍需看画面和素材来源。

素材命名越清楚，当前匹配越稳。例如：

- `01-hook-cleaning.mp4`
- `02-pain-window-dust.mp4`
- `03-feature-extendable-brush.mp4`
- `04-evidence-before-after.mp4`
- `05-cta-order-reminder.mp4`

没有真实素材时，可以先生成本地合成样例：

```powershell
python scripts/generate_fixtures.py --output fixtures
```

## 快速运行

跑产品带货样例：

```powershell
python -m jianji_flow run --mode product --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --work-dir out\scenario-a-product --target-width 320 --target-height 180 --target-fps 12
```

跑口播切片样例：

```powershell
python -m jianji_flow run --mode talking-head --reference fixtures\scenario-b-talking\reference.mp4 --assets fixtures\scenario-b-talking\assets --script fixtures\scenario-b-talking\transcript.txt --work-dir out\scenario-b-talking --target-width 320 --target-height 180 --target-fps 12
```

## 输出文件

- `manifest.json`: local asset inventory.
- `diagnosis.md`: product material readiness report from filename/duration screening, with source preflight warnings or failures when found. `CANDIDATE` means the clip can be tried in a rough cut; it is not visual proof. It also warns when different filenames have byte-identical media or when close-duration candidates look visually similar. When `--visual-selections` is supplied, it explicitly records that visible choices replace filename role matching instead of calling opaque files missing.
- `recipe.json`: authoritative timeline.
- `matches.json`: selected assets, confidence, and evidence.
- `captions.srt`: editable subtitle file.
- `captions.ass`: styled subtitle file used for burn-in.
- `voiceover.wav`: generated machine voiceover.
- `remix.mp4`: rendered preview video.
- `contact-sheet.png`: one representative frame per segment.
- `shot-contact-sheet.png`: one labeled frame per final rendered shot when `--multi-shot` is enabled.
- `reference-comparison.png`: relative samples from the reference and remix for visible before/after checking.
- `shot-plan.json`: final source boundaries and fallback status when `--multi-shot` is enabled; scene boundaries are structural evidence only.
- `candidate-review.html`: side-by-side visual review of weak segments, current frames, candidate frames, recommendation status, reasons, and warnings.
- `candidate-frames/`: images used by `candidate-review.html`.
- `review.md`: review status and checklist.
- `review.html`: local visual review page.
- `fixes.template.json`: editable repair file for replacing weak or low-confidence segments on the next run.
- `visual-similarity-diagnostics/`: sampled frames used to audit visually similar or unchecked repair recommendations.
- `change-diagnostics/`: before/after sampled frames used by the `Change report` after a fix run.
- `visual-candidates.json`: candidate windows and three sampled frames per candidate.
- `visual-candidate-sheet.png`: contact sheet for choosing candidates without relying on file names.
- `visual-selection.template.json`: starter JSON for recording a reviewer, candidate id, and reason for each selected segment.
- `visual-selection-evidence/`: self-contained candidate sheet and selected frames copied into a rendered run's review folder.
- `source-diversity-diagnostics/`: sampled frame comparisons used when assets may be re-encoded, cropped, or partial overlaps from one source.

`review.md` and `review.html` also include a `Storyboard` section. It lists each segment's role, caption, selected asset, source range, matching evidence, and risk, so a user can see what was cut without opening `matches.json`.
When fixes are generated, open `candidate-review.html` from the same work directory. It shows the current segment frame next to up to three candidate frames, including whether a candidate is a clean recommendation, a warning-only option, or a wrong-role manual-inspection fallback.
After rerunning with `--fixes` or `--apply-recommendation`, open the `Change report` section in `review.md` or `review.html`. It lists the changed segment, before/after asset, before/after source range, override reason, before/after sampled frames, and `Picture change`. `Picture change` only means sampled frames differ; it does not prove the new shot fits the script.

## Visual Shot Selection

When filenames are opaque, or the first rough cut is only a voiceover shell, run the visual review pass before rendering:

```powershell
python -m jianji_flow visual-review --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --work-dir out\visual-board
```

Open `visual-candidate-sheet.png`. In a Codex run, Codex inspects the board, writes a new selection JSON with a candidate id and a short reason only for genuinely supported segments, then reruns:

```powershell
python -m jianji_flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --visual-selections out\visual-board\visual-selections.json --work-dir out\visual-selected
```

For a more visibly paced draft, add `--multi-shot`. It detects bounded scene changes inside selected source windows, renders each safe range as a separate shot, and records the final retimed boundaries in `shot-plan.json`. Low-confidence matches are deliberately kept as one source window until visual review confirms the material:

```powershell
python -m jianji_flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --visual-selections out\visual-board\visual-selections.json --multi-shot --work-dir out\visual-selected-multi-shot
```

The shot plan also warns when adjacent segments repeat the same source shot sequence. Keep that warning visible until the adjacent footage is intentionally distinct or the repetition has been manually accepted.

This option is intentionally opt-in while it is being validated on more real material. It can improve pacing, but it does not prove that a scene boundary matches the spoken claim; inspect `remix.mp4`, `contact-sheet.png`, `shot-plan.json`, and `review.html` together.

The selection is checked against the candidate manifest, asset fingerprint, source range, and sampled-frame fingerprints before rendering. Leave a segment unselected when no candidate truly supports its caption; the run should remain `warning` and the review page will name the missing story evidence. A visual change proves only that the selected window changed, not that the product claim is true. The final `reference-comparison.png` is the fastest check that the remix is visibly different from the reference.

## 状态怎么理解

| 状态 | 能不能继续用 | 必须怎么做 |
| --- | --- | --- |
| `pass` | 可以进入人工发布前复核 | 仍要看 `remix.mp4`、`contact-sheet.png` 和商品信息 |
| `warning` | 只能当作待确认粗剪 | 按警告检查或替换素材，不要直接发布 |
| `fail` | 不应使用输出视频 | 根据 `review.md`、`diagnosis.md` 或诊断图修复后重跑 |

`warning` 不是“基本通过”。它只说明工作流产出了可检查的粗剪，但仍有证据不足、素材风险或人工确认项。如果多个片段的源画面都出现平台 UI/旧字幕风险，预检会在配音和渲染前升级为 `fail`，避免先生成一条看似完成但不能发布的视频。

## Story Support

`review.md` and `review.html` include a `Story support` section.

- `pass`: selected clips have stronger evidence than file names for the story roles.
- `weak`: one or more story roles are selected only by file names, fallback choice, or no visual evidence. Follow the `next_action`, then open `contact-sheet.png` and confirm the product story manually.
- `fail`: no selected clips support the story. Do not use the output.

Current matching is intentionally conservative. On real local素材, `weak` is common because the tool can assemble role-labeled clips but cannot yet truly see and understand the product story.

## Segment Fixes

When `Story support` is `weak`, Codex opens `fixes.template.json`, fills only the `asset_path` for a genuinely appropriate replacement, leaves the other entries blank, and reruns with `--fixes`. The user should not need to edit JSON.

Example:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --fixes out\jianji-flow-quick\fixes.template.json
```

To apply one clean recommendation without editing JSON, pass the segment id:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --fixes out\jianji-flow-quick\fixes.template.json --apply-recommendation seg-003
```

Blank `asset_path` entries are ignored. Each segment also includes `recommended_asset_path`, optional `recommended_source_start_ms`, `recommendation_status`, and scored `candidate_assets`; when the best available option would repeat an adjacent source, reuse a different window from the same source file, look visually similar to the current segment, or fail visual checking, the status becomes `best_available_with_warnings` instead of pretending the recommendation is clean. `candidate_asset_paths` is only a compact compatibility summary; use `candidate_assets.source_start_ms` and `candidate_assets.source_end_ms` for real review when a file appears more than once. A filled path that does not exist in the scanned asset folder, a too-short replacement clip, an invalid `source_start_ms`, or an unknown segment/role fails clearly and writes the reason to `review.md`. After rerun, check the `Change report` first, then compare `contact-sheet.png` to confirm the replaced segment actually changed.
`--apply-recommendation` only accepts `recommendation_status: recommended`; it fails clearly for `best_available_with_warnings` or `no_candidate`.
If `recommendation_status` is `no_candidate`, do not copy a fallback candidate blindly. It means no duration-ready same-role replacement was found; add or choose clearer material for that story role instead. `candidate_assets` can still show wrong-role clips for manual inspection, but they include `role_match: false` and a role-mismatch warning.

Visual similarity checking samples three frames from the actual selected source window and the candidate clip. It is a guard against duplicate-looking replacements, not proof that the clip semantically matches the script.
`candidate-review.html` makes those repair choices visible. Use it to see what the system might change before editing JSON or applying a recommendation; if the page shows role mismatch, same-source-window, frame-unavailable, or visually similar warnings, treat the candidate as manual review only.

## 怎么判断结果能不能用

每次运行后，先打开 `review.html`，再看 `remix.mp4`。

重点检查：

- `review.md` 的状态是 `pass` 或 `warning`，不是 `fail`。`warning` 不是可直接发布，它表示需要人工确认。
- `contact-sheet.png` 里每一段都有不同画面，不是纯色背景或空白图。
- `remix.mp4` 有声音，字幕可读，画面没有明显黑屏、卡帧或严重拉伸。
- `matches.json` 里的素材路径确实来自你的 `assets/` 文件夹。
- 如果报告出现 `filename-only`，说明系统只是按文件名角色组装，必须看 `contact-sheet.png` 确认画面是否真的对上文案。
- 如果报告出现 `visual_similarity_diagnostics`，说明有推荐被视觉相似或无法确认降级，先看诊断图再决定是否手动替换。
- 如果 `Story support` 是 `weak`，说明这条视频可能只是按角色拼接，还没有足够证据证明产品故事成立。先看 `next_action` 里点名的角色，替换或人工确认对应素材，再确认开头、痛点、卖点、证据、行动提醒是否都被画面支撑。
- 如果报告出现 `source_diagnostics` 或 `source-diagnostics`，说明源素材预检发现问题，优先替换对应素材；同一源视频在多个片段中复用不会被重复计数，但同一片多个采样点持续报警仍会拦截渲染。
- 如果使用了视觉选择，先看 `review.html` 的 `Visual selection` 区域，确认每个候选画面和选择理由；如果某个角色没有选择记录，不要把它当成自动理解成功。

## Validation

The release and business gates are documented in
[`docs/launch-and-business.md`](docs/launch-and-business.md). The intended
order is quality evidence, public free core, paid manual delivery, and only
then repeated paid product layers.

```powershell
python -m pytest -q
python scripts/run_smoke.py
python scripts/run_p0.py
```

Latest local result:

- `python -m pytest -q` -> 384 passed
- `python scripts/run_smoke.py` -> smoke passed
- `python scripts/run_p0.py` -> p0 passed
- `python -m jianji_flow --version` -> `jianji-flow 0.3.0.dev0`
- the latest real-material A/B run keeps low-confidence segments as one source
  window; the better feature candidate removes the identical adjacent shot
  sequence, but the run remains `warning` until dirty source frames are
  replaced;

## Safety Rules

- Warning runs print `jianji-flow review required`, not `completed`.
- Reference video picture and audio are never copied into `remix.mp4`.
- URL, protocol, protocol-relative, and network paths are rejected.
- Outputs must stay inside the requested work directory.
- Blocking failures remove stale success artifacts.
- Failed artifact review keeps diagnostic screenshots when they explain the failure.
- `review.md` must report failures and warnings honestly.

## Known Limitations

- 当前默认使用 Windows 本地中文 TTS；没有中文语音包的机器会失败。
- 当前匹配主要依赖文件名、结构和可审计证据，不是完整多模态理解。
- 视觉相似检查只比较采样帧；它能减少重复画面修复建议，但不能证明语义匹配。
- 当前不会自动寻找素材、生成素材、发布视频或创建剪映草稿。
- 字幕字体默认使用 `Microsoft YaHei`；非 Windows 环境需要后续适配字体。
- `remix.mp4` 是自动剪辑预览，发布前仍需要人工复核。

## Contract Note

The package is currently the `0.3.0.dev0` development preview, but the JSON recipe contract still uses `"version": "0.1"` for compatibility with the v0.1 schema. The current experience adds optional fields such as:

- `audio_strategy: "voiceover-only"`
- `voiceover_path`
- `caption_burn_in: true`

## License

MIT
