# Agent 打造说明

更新日期：2026-08-31

## 第一版 Agent 要完成的工作

第一版只有一名 Agent 和一条业务主线；范围确认、例外处理和最终采用都由企划人员把关。

```text
企划人员确认下周问题
        ↓
Agent 读取本次材料并核对版本
        ↓
Agent 合并事件、判断优先级、生成企划结果
        ↓
企划人员查看来源，采用、退回或要求补证
```

### 最小链路的实现约束

2026-08-31 的逻辑原型确认，第一版只需要记录一条有界阶段链：读取材料、核对版本、合并事件、形成调查计划、选择本地白名单动作、读取工具反馈、生成结果、最多修正一次、等待人工复核。正式实现不引入通用工作流引擎；程序必须拒绝阶段外跳转，并由结果校验强制 `external_actions` 为空、复核状态为 `awaiting_human_review`。发送、发布、投放和预算变更不属于这条状态链，也不注册为本场景工具。

模型的价值在于处理材料之间的关系和业务语境；稳定规则由程序保证。去重键、来源字段、卡片引用、日期范围和“禁止自动外发”等规则不交给模型自由发挥。

### 架构判断与当前薄弱处

当前实现是代码原生的受约束单 Agent 工作流，不是 Dify。Dify 是可选编排平台，不是 Agent 定义；V1 不为改变外观迁移平台，也不增加多 Agent。

Day 1–2 当前可以称为真实 Key 跑通的可运行骨架，但不能称为完整成熟 Agent。历史 `schema_version=1.0` 曾用真实 DeepSeek Key 生成通过专用校验的 JSON；当前 `schema_version=1.1` 已加入有界闭环，并已用 DeepSeek `deepseek-v4-flash` 跑通默认周报和库迪目标变体。主演示默认周报 `100927` 用时 27.6 秒，产出 7 张情报卡、3 条 Brief、3 个调查动作，首轮生成即通过；库迪变体的调查路径转向库迪缺证与快闪关联。17:50 左右程序合成 `adjustment_reasons` 的文件仍不得作为演示证据。

### 当前 Agent 性验收门

当前代码线的验收门就是一个有界闭环，不引入实时抓取、通用工作流引擎或无限 ReAct：

```text
营销目标
  → 观察本地材料与当前缺口
  → Agent 记录调查计划并从白名单选择必要动作
  → 程序执行本地查证 / 版本比较 / 竞品对比 / 冲突核对
  → Agent 读取反馈并生成周企划结果
  → Brand Radar 专用校验
  → 失败时最多反馈修正一次
  → 人工复核或明确失败
```

程序仍强制来源范围、最大动作数、最大一次修正、原子落盘和外部动作禁令。调查计划、所选动作、工具反馈摘要和调整理由进入运行记录，便于判断变化来自真实调查路径，而不是固定 JSON 模板。当前默认周报和库迪目标变体已经提供初步路径差异证据；后续仍要继续扩大来源包质量、图像素材、人工复核体验和交互入口。

## 人、模型和程序如何分工

### 企划人员

- 说明品牌、竞品、地区、时间和业务问题。
- 提供材料并声明品牌安全边界。
- 处理版本冲突、低证据结论和敏感事项。
- 决定 Brief 是否采用以及是否进入后续执行。

### 模型

- 判断材料是否与本次任务相关。
- 识别不同材料之间的版本、补充和冲突关系。
- 在规则允许的范围内判断“本周跟进 / 继续观察 / 主动避开 / 待核”。
- 用企划语言解释理由并起草三条不同的 Brief 角度。

### 程序

- 读取材料清单并保留来源、日期和类型。
- 按稳定字段合并明显重复项，检查卡片与 Brief 的引用关系。
- 限制执行轮次和重复调用，记录失败原因。
- 区分真实模型、Mock、Replay、人工补充和公开来源。
- 在任何发送、发布、投放或预算动作之前停止。

## 两个不要混淆的选择

材料来自哪里，与是否使用真实模型是两件事：

| 选择 | 第一版用途 |
|---|---|
| Replay 材料 | 稳定复现同一批业务输入，便于演示和回归 |
| 人工补充材料 | 接收使用者提供的公开链接、文件或摘录 |
| 实时公开来源 | 后续按需要增加；不阻塞第一版 |
| 真实模型 API | 第一版完整 Agent 流程的必验路径 |
| Mock | 无 Key 时检查程序链路，不能作为业务结果 |

第一版验收组合是“真实模型 API + Replay / 人工补充材料”。因此不需要先解决全网实时抓取，也不能用静态 Replay 页面替代模型实际判断。

## 现有代码可以复用什么

- `run.py` 已有统一 CLI 入口和 Provider 配置检查，可继续作为启动入口。
- `framework/llm_client.py` 已支持 OpenAI、Anthropic、DeepSeek、Moonshot 和 Zhipu，并有 OpenAI-compatible 与 Anthropic 两条调用路径。
- `framework/agent_runner.py` 已有场景识别、工具加载、最大轮次、重复调用保护、上下文压缩和执行记录。
- `framework/output_schema.py` 已有“事实 → 洞察 → 建议”的引用基础，可以复用其校验思路。
- `v3_agent/tools.py` 与 `scenarios/tools_real.py` 提供早期工具定义和执行方式，当前仍被 Runner 直接引用，暂不物理搬动。

这些旧代码仍只是基础能力；Day 1–2 已通过独立的 `brand_radar_weekly` 入口把当前产品收敛为单一周企划流程，未删除或迁移旧场景。

## Day 1–2 落地状态

1. `--require-api` 已实现；缺 Key、错误 Key 或模型失败都会明确停止，不静默降级 Mock。
2. `brand_radar_weekly` 已加入注册表；四个固定证据预处理阶段为 `read_weekly_settings`、`read_weekly_source_pack`、`resolve_weekly_versions`、`merge_weekly_events`。
3. 当前 `schema_version=1.1` 让模型在预处理后记录调查计划，并从本地白名单中选择 1–4 个动作：`inspect_local_evidence`、`compare_event_versions`、`compare_competitor_evidence`、`cross_check_conflicting_evidence`。
4. weekly 不调用旧外部工具、飞书或历史写入器，只读取观察包、生成结果并停在人工复核前。
5. `framework/brand_radar_output.py` 已新增情报卡、日历、关键词、Brief、来源、调查轨迹与人工复核的专用校验。
6. Replay、PUBLIC、MANUAL、Mock 与 real 状态分别保留在观察包和输出元数据中。
7. 当前 `schema_version=1.1` 真实默认周报主演示成功：`outputs/brand_radar_weekly-real-20260901-100927-543102.json` 与同名 HTML，27.6 秒，7 卡 / 3 Brief，3 个调查动作，首轮生成即通过，`awaiting_human_review`，`external_actions=[]`。此前 `004131` 只作为旧证据保留。
8. 库迪目标变体成功：`outputs/brand_radar_weekly-real-20260901-001559-688407.json` 与同名 HTML，调查路径转向库迪缺证与快闪关联，并生成缺证卡供人工复核。
9. 错误 Key 0.7 秒退出码 3，明确失败，没有新增 JSON / HTML / tmp，没有降级 Mock。
10. 当前测试数为 73。

## 最小实现方式

沿用现有 Runner，不先重写框架。新增内容保持在少量清楚文件中：

```text
data/replay/coffee-week-2026-09-07/
  manifest.json            # 材料清单、来源、日期和类型
  sources/                 # Replay 正文或摘录

scenarios/
  brand_radar_weekly.py    # 本场景工具：读材料、合并、排序、生成日历与 Brief

framework/
  brand_radar_output.py    # 情报卡、日历、关键词、Brief 和运行信息的校验
  brand_radar_report.py    # 从同一 JSON 生成本地 HTML 周会稿

outputs/                   # 本机运行结果，不提交 Git
```

同时只做三处小改动：

- 在 `framework/scenario_registry.json` 增加唯一当前场景 `brand_radar_weekly`。
- 在 `framework/agent_runner.py` 注册新工具来源，并让该场景使用专用结果校验。
- 在 `run.py` 增加清楚的周企划入口、材料包参数、`--require-api` 验收开关和同源 HTML 生成提示。

旧场景继续留在 Git 历史和现有目录中，但 README 不再把它们当成当前产品入口。等新入口通过真实 API 和 Dashboard 验收后，再单独做物理迁移。

## 第一版工具职责

工具数量保持小，名字表达业务动作：

- 读取观察设置：返回品牌、竞品、地区、时间、关键词和业务问题。
- 读取材料包：按清单返回材料正文与来源信息，不访问清单外的私有内容。
- 核对材料版本：标出最新有效、被覆盖、过期、无关和冲突项。
- 合并营销事件：把同一事件的多份材料归到一张卡，保留所有来源。
- 形成周企划结果：根据已核卡片生成优先级、日历、关键词和 Brief。

“形成周企划结果”可以由模型判断，但程序必须在最终返回前检查：卡片 ID 唯一、来源存在、Brief 引用有效、日期格式正确、来源类型明确、对外动作为空。

## 一份结果至少包含什么

- 本次观察设置和使用的模型、材料类型。
- 读取成功、读取失败和被排除的材料清单。
- 版本取舍与冲突说明。
- 情报卡：事实、优先级、理由、来源、风险和待核项。
- 30 天日历与关联卡片。
- 重点关键词与关联卡片。
- 三条 Brief 与引用卡片。
- 人工复核项和运行失败原因。

本地 HTML 周会稿直接读取这份结果，不另写静态 Brief。这样 CLI 和页面展示的是同一次 Agent 工作。交互 Dashboard / chat 是下一阶段候选，不是当前 Day 1–2 必须完成项。

当前唯一 canonical 结果是校验通过后原子写入 `outputs/brand_radar_weekly-<mode>-<timestamp>.json` 的 JSON。HTML 周会稿、未来 GUI chat、报告和 Dashboard 都是读取或解释这份 artifact 的入口；当前 CLI 没有 GUI chat、交互 Dashboard、自动刷新或实时抓取。

## API Key 和本机状态

- Key 只放在 Mac Mini 本机 `.env` 或系统环境变量，不写入参数、日志、截图、输出 JSON、交接文件或 Git。
- `.env.example` 只保留变量名和空值。
- 启动信息只显示 Provider、模型和“已配置 / 未配置”，不显示 Key 内容。
- 真实模式请求失败时记录错误类别和发生环节，不记录请求头。
- 新电脑重新安装依赖并用服务商原生方式配置 Key；不复制 `.venv`、缓存、Keychain 或 Codex 状态库。

## 开发顺序

1. 先定好观察包和结果样例，人工检查来源、版本、重复项、待核项和三条 Brief 的关系。
2. 接入 `brand_radar_weekly`，用 Mock 跑一次只确认工具顺序、引用校验和失败处理。
3. 使用真实测试 Key 跑完整链路，确认模型确实读取材料、选择调查动作、读取反馈并产生随输入变化的结果。
4. 用关键词、竞品和矛盾材料变化验收路径差异；错误 Key 必须明确失败且不降级 Mock。
5. 从同一 JSON 生成本地 HTML 周会稿，覆盖重点、Brief、未来 30 天关键节点、关键词、调查理由、来源和人审。
6. 下一阶段再评估交互 Dashboard / chat，补上筛选、来源展开和采用 / 退回 / 补证操作。
7. 完成断网、材料缺失和引用错误等剩余异常路径验收。

详细五天安排见 [开发计划](ROADMAP.md)。

## 目标命令

以下是当前已支持并已用真实 Key 跑通的验收入口：

```bash
python3 run.py --weekly \
  --source-pack data/replay/coffee-week-2026-09-07/manifest.json \
  --require-api
```

验收通过时应显示真实 Provider、材料包、输出位置和人工复核提示。若缺少 Key，应在开始处理材料前失败；如果主动去掉 `--require-api`，才允许进入清楚标记的 Mock 烟雾测试。
