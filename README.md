# jianji-flow

`jianji-flow` 是一个开源 Codex 自动剪辑 skill：输入参考视频、本地素材目录和可选文案，输出一条可人工复核的短视频粗剪预览。

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
- Generates `captions.srt` and `captions.ass`.
- Generates `voiceover.wav` with a local Windows Chinese TTS voice when available.
- Renders `remix.mp4` with burned-in captions and voiceover audio.
- Writes `contact-sheet.png` with one frame per timeline segment.
- Writes `review.md` and `review.html` for manual inspection.
- Shows `CANDIDATE` in `diagnosis.md` for filename/duration-ready clips, because that is not visual proof.
- Marks filename-only matching as `warning` because it does not prove visual understanding.
- Adds a `Story support` review section that warns when most story roles have no non-filename visual evidence.

## What It Does Not Do

- It does not create Jianying or CapCut draft projects.
- It does not build a full desktop editing application.
- It does not search online for assets.
- It does not publish videos.
- It does not preserve source audio by default.
- It does not generate music, effects, or beat-synced edits.
- It does not truly decompose a viral reference video into camera moves, hooks, or pacing yet.
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

`quick` 在没有传 `--script` 时会使用一组很短的家居生活用品默认文案。默认文案只适合清洁类家居样例；如果是收纳、厨房、床品、灯具等其他产品，请传入自己的 `--script`。产品模式每次都会写出 `diagnosis.md`，先说明素材只是通过文件名和时长初筛；素材明显不够时，它会先停下，不会硬剪出一条误导性的坏视频。

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
- `diagnosis.md`: product material readiness report from filename/duration screening, with source preflight warnings or failures when found. `CANDIDATE` means the clip can be tried in a rough cut; it is not visual proof.
- `recipe.json`: authoritative timeline.
- `matches.json`: selected assets, confidence, and evidence.
- `captions.srt`: editable subtitle file.
- `captions.ass`: styled subtitle file used for burn-in.
- `voiceover.wav`: generated machine voiceover.
- `remix.mp4`: rendered preview video.
- `contact-sheet.png`: one representative frame per segment.
- `review.md`: review status and checklist.
- `review.html`: local visual review page.
- `fixes.template.json`: editable repair file for replacing weak or low-confidence segments on the next run.

`review.md` and `review.html` also include a `Storyboard` section. It lists each segment's role, caption, selected asset, source range, matching evidence, and risk, so a user can see what was cut without opening `matches.json`.

## 状态怎么理解

| 状态 | 能不能继续用 | 必须怎么做 |
| --- | --- | --- |
| `pass` | 可以进入人工发布前复核 | 仍要看 `remix.mp4`、`contact-sheet.png` 和商品信息 |
| `warning` | 只能当作待确认粗剪 | 按警告检查或替换素材，不要直接发布 |
| `fail` | 不应使用输出视频 | 根据 `review.md`、`diagnosis.md` 或诊断图修复后重跑 |

`warning` 不是“基本通过”。它只说明工作流产出了可检查的粗剪，但仍有证据不足、素材风险或人工确认项。

## Story Support

`review.md` and `review.html` include a `Story support` section.

- `pass`: selected clips have stronger evidence than file names for the story roles.
- `weak`: one or more story roles are selected only by file names, fallback choice, or no visual evidence. Follow the `next_action`, then open `contact-sheet.png` and confirm the product story manually.
- `fail`: no selected clips support the story. Do not use the output.

Current matching is intentionally conservative. On real local素材, `weak` is common because the tool can assemble role-labeled clips but cannot yet truly see and understand the product story.

## Segment Fixes

When `Story support` is `weak`, open `fixes.template.json`. Fill only the `asset_path` for the segment you want to replace, leave the other blank entries as they are, then rerun with `--fixes`.

Example:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --fixes out\jianji-flow-quick\fixes.template.json
```

To apply one clean recommendation without editing JSON, pass the segment id:

```powershell
jianji-flow quick --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --fixes out\jianji-flow-quick\fixes.template.json --apply-recommendation seg-003
```

Blank `asset_path` entries are ignored. Each segment also includes `recommended_asset_path`, `recommendation_status`, and scored `candidate_assets`; when the best available option would repeat an adjacent source, the status becomes `best_available_with_warnings` instead of pretending the recommendation is clean. A filled path that does not exist in the scanned asset folder, a too-short replacement clip, or an unknown segment/role fails clearly and writes the reason to `review.md`. After rerun, check `matches.json` for `override:seg-xxx` or `override:role:xxx`, then compare `contact-sheet.png` to confirm the replaced segment actually changed.
`--apply-recommendation` only accepts `recommendation_status: recommended`; it fails clearly for `best_available_with_warnings` or `no_candidate`.
If `recommendation_status` is `no_candidate`, do not copy a fallback candidate blindly. It means no duration-ready same-role replacement was found; add or choose clearer material for that story role instead. `candidate_assets` can still show wrong-role clips for manual inspection, but they include `role_match: false` and a role-mismatch warning.

## 怎么判断结果能不能用

每次运行后，先打开 `review.html`，再看 `remix.mp4`。

重点检查：

- `review.md` 的状态是 `pass` 或 `warning`，不是 `fail`。`warning` 不是可直接发布，它表示需要人工确认。
- `contact-sheet.png` 里每一段都有不同画面，不是纯色背景或空白图。
- `remix.mp4` 有声音，字幕可读，画面没有明显黑屏、卡帧或严重拉伸。
- `matches.json` 里的素材路径确实来自你的 `assets/` 文件夹。
- 如果报告出现 `filename-only`，说明系统只是按文件名角色组装，必须看 `contact-sheet.png` 确认画面是否真的对上文案。
- 如果 `Story support` 是 `weak`，说明这条视频可能只是按角色拼接，还没有足够证据证明产品故事成立。先看 `next_action` 里点名的角色，替换或人工确认对应素材，再确认开头、痛点、卖点、证据、行动提醒是否都被画面支撑。
- 如果报告出现 `source_diagnostics` 或 `source-diagnostics`，说明源素材预检发现问题，优先替换对应素材。

## Validation

```powershell
python -m pytest -q
python scripts/run_smoke.py
python scripts/run_p0.py
```

Latest local result:

- `python -m pytest -q` -> 310 passed
- `python scripts/run_smoke.py` -> smoke passed
- `python scripts/run_p0.py` -> p0 passed

## Safety Rules

- Reference video picture and audio are never copied into `remix.mp4`.
- URL, protocol, protocol-relative, and network paths are rejected.
- Outputs must stay inside the requested work directory.
- Blocking failures remove stale success artifacts.
- Failed artifact review keeps diagnostic screenshots when they explain the failure.
- `review.md` must report failures and warnings honestly.

## Known Limitations

- 当前默认使用 Windows 本地中文 TTS；没有中文语音包的机器会失败。
- 当前匹配主要依赖文件名、结构和可审计证据，不是完整多模态理解。
- 当前不会自动寻找素材、生成素材、发布视频或创建剪映草稿。
- 字幕字体默认使用 `Microsoft YaHei`；非 Windows 环境需要后续适配字体。
- `remix.mp4` 是自动剪辑预览，发布前仍需要人工复核。

## Contract Note

The package is v0.2.0, but the JSON recipe contract still uses `"version": "0.1"` for compatibility with the v0.1 schema. The v0.2 experience adds optional fields such as:

- `audio_strategy: "voiceover-only"`
- `voiceover_path`
- `caption_burn_in: true`

## License

MIT
