# jianji-flow

`jianji-flow` 是一个开源 Codex 自动剪辑 skill：输入参考视频、本地素材目录和可选文案，输出可审核的预览视频工作流。

它的 v0.1 目标很窄：先把“能稳定生成、能复查、失败不伪成功”的自动剪辑底座跑通。

English summary: `jianji-flow` is an open-source Codex skill for creating auditable preview-video workflows from a reference video, a local asset directory, and optional script text.

## v0.1 能做什么

- 生成 `manifest.json`、`recipe.json`、`matches.json`、`captions.srt`、`remix.mp4`、`review.md`。
- 支持 `product` 和 `talking-head` 两种基础结构。
- 用 JSON Schema 和语义校验阻断路径越界、参考视频泄漏、时间线错误和缺失素材。
- 失败重跑时不会留下旧的误导性 `remix.mp4`。
- 自带合成测试素材，不依赖真实素材或联网下载。

## v0.1 不做什么

- 不生成剪映草稿，也不生成 CapCut 草稿。
- 不把参考视频画面或音频放进输出。
- 不联网找素材，不自动发布视频。
- 不做 TTS、配乐、复杂特效、字幕烧录或图片循环渲染。
- 当前预览视频使用静音音轨，字幕以独立 `captions.srt` 输出。

## 环境要求

- Python 3.10+
- FFmpeg 和 ffprobe

检查环境：

```powershell
python scripts/check_env.py
```

当前这个工作区的 Python 没有 `pip` 模块，所以没有完成 `python -m pip install -e .` 验证；所有命令均已通过 `python -m jianji_flow ...` 和测试环境验证。

## 快速开始

生成本地合成样例：

```powershell
python scripts/generate_fixtures.py --output fixtures
```

跑产品种草样例：

```powershell
python -m jianji_flow run --mode product --reference fixtures\scenario-a-product\reference.mp4 --assets fixtures\scenario-a-product\assets --script fixtures\scenario-a-product\script.txt --work-dir out\scenario-a-product --target-width 320 --target-height 180 --target-fps 12
```

跑口播切片样例：

```powershell
python -m jianji_flow run --mode talking-head --reference fixtures\scenario-b-talking\reference.mp4 --assets fixtures\scenario-b-talking\assets --script fixtures\scenario-b-talking\transcript.txt --work-dir out\scenario-b-talking --target-width 320 --target-height 180 --target-fps 12
```

## 验证

```powershell
python -m pytest -q
python scripts/run_smoke.py
python scripts/run_p0.py
python path\to\quick_validate.py path\to\jianji-flow
```

最近一次本地验证结果：

- `python -m pytest -q` -> 142 passed
- `python scripts/run_smoke.py` -> smoke passed
- `python scripts/run_p0.py` -> p0 passed
- Codex skill quick validation -> Skill is valid

## 输出说明

- `manifest.json`：素材清单和媒体元信息。
- `recipe.json`：唯一权威时间线。
- `matches.json`：素材匹配、置信度和证据。
- `captions.srt`：独立字幕文件。
- `remix.mp4`：校验通过后生成的预览视频。
- `review.md`：状态、阻断项、警告项和人工复核清单。

## License

MIT
