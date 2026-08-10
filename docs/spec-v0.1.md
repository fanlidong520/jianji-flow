# jianji-flow v0.1 规格说明

## 一句话定位
`jianji-flow` 是一个开源 Codex skill，用 Codex、Python 和 FFmpeg 把参考视频、素材库和可选文案自动整理成可审核的预览视频生产线。

## v0.1 目标
v0.1 做一件事：稳定生成可审核的预览视频。

输入：
- 参考视频。
- 素材库目录。
- 可选文案。
- 模式：`product` 或 `talking-head`。

输出：
- `recipe.json`
- `matches.json`
- `captions.srt`
- `remix.mp4`
- `review.md`

输出状态规则：
- `pass`：所有片段都有合法素材，置信度达标，生成全部五个产物。
- `warning`：所有片段都有合法素材，但存在低置信度、缺文案、规格归一化等可审核问题，生成全部五个产物。
- `fail`：存在缺素材、非法路径、参考视频泄漏、时间线越界、损坏关键媒体等阻断问题；生成 `review.md` 和可用的中间诊断文件，但不得生成误导性的 `remix.mp4`。

## 非目标
v0.1 不做以下事项：
- 不生成剪映草稿。
- 不接入 `AI Companion` 桌面应用。
- 不做 TTS、声音克隆、口型同步。
- 不联网找素材。
- 不自动发布视频。
- 不做复杂转场、特效、BGM 自动编排。
- 不保证生成爆款，只保证流程可复跑、产物可审核、问题可暴露。

## 适用场景

### A：产品种草/带货
目标结构：
`hook -> pain -> feature -> evidence -> CTA`

文案含义：
- 用作文案事实约束。
- 用作屏幕字幕来源。
- 不能凭素材外观编造产品功效。

### B：口播课/长视频切片
目标结构：
`topic -> claim -> explanation -> evidence -> conclusion`

文案含义：
- 用作选题、提纲或字幕纠错。
- 如果没有文案或转写稿，v0.1 只能生成结构性预览，并在 `review.md` 标记 `semantic_context_unverified`；不得声称完成语义级切片。
- 输出必须保留观点上下文，不能为了节奏剪断语义。

## 架构
推荐架构：

```text
输入校验 -> 媒体索引/转写 -> 参考结构拆解 -> 素材匹配
       -> JSON Schema 校验 -> FFmpeg 渲染 -> 自动审核
```

职责边界：
- `SKILL.md`：编排流程、询问缺失参数、指导错误处置。
- Python 脚本：环境检查、ffprobe、媒体索引、抽帧、时间线生成、schema 校验、SRT 生成、审核。
- FFmpeg：只消费已经校验通过的时间线，负责确定性渲染。
- Codex：负责理解用户目标、选择模式、解释报告、提出下一步修正。

新增安全校验层：
- JSON Schema 负责字段和类型。
- Python 语义校验负责跨文件一致性、安全边界和时间线规则。
- 渲染器只能消费通过 schema 校验和语义校验的输入。

## 输出契约

### `recipe.json`
唯一权威时间线。要求：
- 时间全部使用整数毫秒。
- 包含 `duration_ms`。
- 包含模式、目标规格、段落角色、字幕、音频策略和 `match_id`。
- 所有片段必须连续、非重叠，且每段 `end_ms > start_ms`。
- 最后一个片段的 `end_ms` 必须等于 `duration_ms`。
- 不允许未知字段。
- 不允许引用参考视频作为成片素材。

### `matches.json`
匹配证据文件。要求：
- 每条记录包含 `status`：`selected`、`low_confidence`、`missing` 或 `rejected`。
- 记录候选素材、选中区间、分项置信度、淘汰原因。
- `selected` 和 `low_confidence` 必须引用 manifest 中存在的素材 ID。
- `missing` 不得包含可渲染素材区间。
- 不维护第二条时间线。
- 每个选择必须能追溯到真实素材路径和素材 ID。

### `manifest.json`
素材清单文件。要求：
- 每个素材有稳定 `asset_id`、规范化路径、SHA-256、媒体类型、时长、分辨率、帧率、音轨信息。
- 渲染器只能使用 manifest 中的素材。
- 参考视频不得进入 manifest 的可渲染素材集合。

### `captions.srt`
字幕文件。要求：
- UTF-8 编码。
- 序号连续。
- 时间轴单调不重叠。
- 不明显超过视频总时长。

### `remix.mp4`
预览视频。默认规格：
- H.264。
- `yuv420p`。
- CFR。
- AAC 48kHz。
- 默认烧录字幕，同时保留 `captions.srt`。

### `review.md`
审核报告。必须包含：
- 总状态：pass、warning 或 fail。
- 输入清单。
- 输出清单。
- 阻断项。
- 警告项。
- 低置信度片段。
- 缺素材片段。
- 人工复核清单。

## 强制规则
- 参考视频只能提供结构、节奏、镜头时长、字幕密度。
- 成片不得使用参考视频画面或音频。
- 缺素材时必须报告，不能用无关素材硬凑。
- FFmpeg 命令不得由模型自由拼接；脚本必须用受控参数生成。
- 所有输出必须写入指定工作目录，不能越界写文件。
- 损坏素材必须隔离并写入报告。
- 阻断失败时不得生成 `remix.mp4`。
- 低置信但合法素材可以生成预览，但必须在 `review.md` 中标出。
- 拒绝 URL、协议输入、输出目录逃逸和指向工作区外的临时文件。

## v0.1 目录建议

```text
jianji-flow/
  SKILL.md
  agents/
    openai.yaml
  scripts/
    check_env.py
    init_project.py
    scan_media.py
    analyze_reference.py
    match_assets.py
    build_recipe.py
    make_srt.py
    render_preview.py
    review_outputs.py
  schemas/
    manifest.schema.json
    recipe.schema.json
    matches.schema.json
  fixtures/
    scenario-a-product/
    scenario-b-talking/
    malformed/
  docs/
    spec-v0.1.md
  task_plan.md
  findings.md
  progress.md
  README.md
  LICENSE
```

## 开发分工
| 阶段 | 主开发 | 审核 | 验收 |
|------|--------|------|------|
| 契约与样例 | gpt-5.6-luna | gpt-5.6-sol + 总控 | schema 固定，未知字段失败 |
| 环境检查与媒体扫描 | gpt-5.6-luna | 总控 | 中文路径、空格路径、损坏素材可处理 |
| 参考视频拆解 | gpt-5.6-luna | gpt-5.6-sol | 只提取结构，不引用参考视频 |
| A/B 模式规划 | gpt-5.6-sol | 总控 | A/B 逻辑独立且可解释 |
| 素材匹配与排程 | gpt-5.6-luna | gpt-5.6-sol + 总控 | 低置信度暴露，不硬凑 |
| SRT 和 MP4 渲染 | gpt-5.6-luna | gpt-5.6-sol | 只从校验后的 recipe 渲染 |
| 自动审核报告 | gpt-5.6-luna | 总控 | 报告说明失败、警告、人工复核项 |
| Skill 封装与开源文档 | 总控 + gpt-5.6-luna | gpt-5.6-sol | 新用户能跑通最小样例 |

## 验证矩阵

### smoke
- A-01：产品种草黄金样例能跑出五个产物。
- B-01：口播切片黄金样例能跑出五个产物。
- O-01：输出完整性检查。
- O-02：`remix.mp4` 可被 ffprobe 解析。

### P0
- A-02：产品种草无文案不崩溃。
- A-03：产品素材不足时明确警告。
- B-02：多个候选片段时能解释选择原因。
- B-03：无文案口播能降级或明确失败。
- I-01：横竖屏和不同帧率输出统一规格。
- I-03：中文字幕编码和时间轴正确。
- I-04：短视频、长视频、空文件边界处理正确。
- N-01：缺少参考视频时明确失败。
- N-02：损坏素材被跳过或明确失败。

### manual-review
人工检查：
- 开头是否快速进入主题。
- 素材是否和文案/旁白匹配。
- 画面有没有黑帧、冻结、严重跳切或变形。
- 字幕是否基本同步、无遮挡、可读。
- 报告是否诚实说明不确定性。

## 发布门槛
- Windows 和 Ubuntu 都能跑通 smoke。
- 黄金样例无需 GPU 即可完成。
- 所有 P0 失败用例不能产生伪成功成片。
- 固定输入重复运行两次，JSON、SRT 和视频关键指标保持一致。
- README 能让新用户从干净环境跑通最小样例。

## 待确认
- GitHub 仓库归属账号或组织。
- v0.1 默认使用 MIT 许可证。
- README 采用中文主文档，加英文摘要。
- CLI 同时支持安装后的 `jianji-flow` 和 `python -m jianji_flow`。
