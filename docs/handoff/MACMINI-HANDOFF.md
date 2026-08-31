# Mac Mini 交接说明

更新日期：2026-08-31

## 交接结论

本仓库已在目标提交 `08704a00e2e3105934b4345154babbd91ff67a4a` 之上完成并验收 Day 1–2 可运行骨架：33 项测试通过，缺 Key 与错误 Key 会明确失败，真实 `deepseek-v4-flash` 默认观察包和关键词变体均生成通过专用校验的结果。流程默认停在人工复核前。

这只通过了“真能跑”硬门，不能称为完整 Brand Radar Agent Demo。当前是代码原生的受约束单 Agent 工作流，不是 Dify；前置阶段由程序固定执行，尚无 Agent 调查计划、白名单工具选择、反馈调整和最多一次校验修正。

第一版目标只做一件事：使用真实模型 API Key 读取咖啡品类 Replay / 人工补充材料，输出下周企划会需要的情报流、30 天日历、重点关键词和 3 条 Brief，并停在人工复核前。

## 开始前先读

按顺序阅读：

1. `README.md`
2. `docs/product/PRD.md`
3. `docs/business/NEXT-WEEK-WORKFLOW.md`
4. `docs/product/AGENT-BUILD.md`
5. `docs/product/ROADMAP.md`
6. `docs/PROJECT-STATE.md`
7. `docs/handoff/MACMINI-HANDOFF.md`（当前文件，用于核对交接边界）

这些文件是当前事实源。历史对话、旧根目录规划稿、V1-V3 示例和 Mock 输出不能覆盖这条主线。

## 已完成

- README 已改成业务入口，说明 V1 必须真实 API Key 跑完整 Agent 流程。
- PRD 已改成营销企划业务流程语言，包含材料、判断、交付和验收。
- 新增 `docs/business/NEXT-WEEK-WORKFLOW.md`，用 `fusion` 从 Accio / RealReplicaBench 原始任务提炼可迁移工作方法，并转译成 Brand Radar 自有流程。
- 新增 `docs/product/AGENT-BUILD.md`，保留“怎么打造 Agent”的工程说明。
- Roadmap 和 Project State 已改成 Mac Mini 可以直接接续的五天计划与缺口清单。
- `.env.example` 已明确 Mock 只用于烟雾测试；`.gitignore` 已忽略 `.env`、`outputs/`、`memory/` 和本地日志。
- 已准备咖啡 Replay 包及人工期望结果，包含重复、版本替换、过期、待核和风险节点。
- 已实现 `brand_radar_weekly`、专用证据链校验和 `--weekly / --source-pack / --require-api`。
- weekly 入口只注册本地只读工具，结果强制 `external_actions=[]` 与 `awaiting_human_review`。
- 故意错误的 DeepSeek Key 已验证为明确鉴权失败，未降级 Mock、未生成结果。
- 真实 DeepSeek 默认观察包生成 7 张情报卡和 3 条不同视角 Brief；三条 Brief 均引用存在的情报卡。
- 只将关键词从 `社区空间` 改为 `早餐通勤` 的真实变体验收产生了可解释变化，没有制造无证据的早餐结论。
- 人工逐卡复核未发现捏造经营数字；“中秋国庆竞品空位”Brief 仍缺竞品节日动作的直接材料，已在输出中标为 missing_evidence，不能把合法引用误写成调查充分。

## 已知事实

- `run.py` 是当前 CLI 入口，现有命令 `python3 run.py --help` 和 `python3 run.py --list` 可作为基线检查。
- `framework/llm_client.py` 支持 OpenAI、Anthropic、DeepSeek、Moonshot 和 Zhipu；weekly 的 `--require-api` 会禁止缺 Key 或请求失败时进入 Mock。
- `framework/agent_runner.py` 已有场景识别、工具调用、轮次限制、重复调用保护和结构化输出解析。
- `framework/scenario_registry.json` 仍保留早期多场景配置，但 `brand_radar_weekly` 只注册四个本地只读阶段，不注册飞书或其他外部写入工具。
- 咖啡 Replay 包、`brand_radar_weekly`、专用结果校验和真实 Key 证据均已具备；Dashboard 尚未实现。

## Mac Mini 下一项任务

Day 1–2 已完成，不在交接时重复调用真实 API。下一阶段只有在用户明确启动后，才补最小有界闭环：“目标 → 观察 → Agent 计划 / 白名单工具选择 → 工具反馈 → 生成 → 专用校验 → 最多一次修正 → 人工复核”。这道硬门通过后再做 Dashboard；不要迁移 Dify，也不要扩张到实时抓取、多 Agent、数据库、账号系统或旧目录迁移。

## 目标命令

当前命令可用于基线检查：

```bash
python3 run.py --help
python3 run.py --list
```

当前已支持：

```bash
python3 run.py --weekly \
  --source-pack data/replay/coffee-week-2026-09-07/manifest.json \
  --require-api
```

验收通过时应显示真实 Provider、模型、材料包、输出位置和人工复核提示。主动去掉 `--require-api` 时，才允许进入清楚标记的 Mock 烟雾测试。

## 原始案例参考边界

只把 RealReplicaBench 当成工作方法来源，不复制任务文案、数据、代码、业务对象或交付物。参考固定版本：

- `https://github.com/Accio-Lab/RealReplicaBench/tree/4041872837eb960a16bbe3d73b459f20680b8ad6`

重点吸收的方法是：先读完整材料、还原最新有效版本、排除旧通知和无关项、只补当前状态缺口、草稿不是事实源、对外动作前停在人审。

## Suggested Skills

- `fusion`：需要继续从多个原始业务案例中抽象可迁移机制时使用。
- `prototype`：开始落地最小可跑 Agent 和 Dashboard 时使用。
- `postflight`：真实 Key 跑通后做收尾验收、证据整理和交付核对时使用。

## 不要做

- 不提交 `.env`、API Key、Cookie、Keychain、`.venv`、缓存、Codex 状态库或运行输出。
- 不把 Mock 输出、Replay 样例或早期静态页面描述成真实业务结果。
- 不强推默认分支。
- 不为了“更像 Agent”迁移 Dify 或增加多 Agent。
- 不移动 `run.py`、`framework/`、`v3_agent/tools.py`、`scenarios/tools_real.py`，直到新入口跑通且回归命令更新。
- 不自动发送飞书、发稿、投放、改预算或调用任何外部写入动作。
