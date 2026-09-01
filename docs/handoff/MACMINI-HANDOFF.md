# Mac Mini 交接说明

更新日期：2026-08-31

## 交接结论

本仓库已在目标提交 `08704a00e2e3105934b4345154babbd91ff67a4a` 之上继续 Day 1–2 可运行骨架。当前 `schema_version=1.1` 已实现有界调查闭环，并用真实 DeepSeek `deepseek-v4-flash` 跑通默认周报和库迪目标变体；结果同时保存 JSON 和同源 HTML 周会稿。流程默认停在人工复核前。

这可以称为 Day 1–2 可运行周会骨架通过，但不能称为完整成熟 Brand Radar Agent。当前是代码原生的受约束单 Agent 工作流，不是 Dify；四个固定证据预处理阶段由程序执行，模型记录调查计划并从本地白名单选择 1–4 个动作，读取反馈后生成，专用校验失败时最多修正一次。亮点是目标驱动调查、受限行动、反馈调整和营销特化；安全边界是基础要求，不是卖点。

第一版目标只做一件事：使用真实模型 API Key 读取咖啡品类 Replay / 人工补充材料，输出下周企划会需要的情报流、30 天日历、重点关键词和 3 条 Brief，并停在人工复核前。

## 交付定位与本机重建

- 私有远端：`https://github.com/Kyoyen/brand-radar-agent.git`
- 目标分支：`docs/lean-demo-cleanup-20260831`
- 起始提交：`08704a00e2e3105934b4345154babbd91ff67a4a`
- 当前可见工作树：有代码、测试和文档变更待提交；不要描述为 clean。`.env`、`.venv`、`outputs/` 和 `.longrun/` 不属于远端交付，也不会跨机迁移。

新机器不要复制 `.venv` 或 Key。当前 weekly 只需要核心依赖；默认源卡住时可切清华源，不必为了旧实时工具先硬装 `lxml`：

```bash
python3 -m venv .venv
$HOME/.codex/bin/longrun --label "Brand Radar weekly core dependencies" \
  --timeout 120 --stall-timeout 30 --max-retries 0 -- \
  .venv/bin/python -m pip install \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  "openai>=1.30.0" "httpx>=0.27.0" "pydantic>=2.0.0" \
  "python-dotenv>=1.0.0" "rich>=13.0.0"
cp .env.example .env
```

在本机编辑 `.env`，只填 Provider、模型和 Key；不要把 Key 放进命令参数或 `longrun` 日志。然后验证：

```bash
$HOME/.codex/bin/longrun --label "Brand Radar regression" \
  --timeout 120 --stall-timeout 30 --max-retries 0 -- \
  .venv/bin/python -m unittest discover -s tests -p 'test_*.py'

$HOME/.codex/bin/longrun --label "Brand Radar real weekly" \
  --timeout 120 --stall-timeout 30 --max-retries 0 -- \
  .venv/bin/python run.py --weekly \
  --source-pack data/replay/coffee-week-2026-09-07/manifest.json \
  --require-api
```

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

## 已完成与当前状态

- README 已改成业务入口，说明 V1 必须真实 API Key 跑完整 Agent 流程。
- PRD 已改成营销企划业务流程语言，包含材料、判断、交付和验收。
- 新增 `docs/business/NEXT-WEEK-WORKFLOW.md`，用 `fusion` 从 Accio / RealReplicaBench 原始任务提炼可迁移工作方法，并转译成 Brand Radar 自有流程。
- 新增 `docs/product/AGENT-BUILD.md`，保留“怎么打造 Agent”的工程说明。
- Roadmap 和 Project State 已改成 Mac Mini 可以直接接续的五天计划与缺口清单。
- `.env.example` 已明确 Mock 只用于烟雾测试；`.gitignore` 已忽略 `.env`、`outputs/`、`memory/` 和本地日志。
- 已准备咖啡 Replay 包及人工期望结果，包含重复、版本替换、过期、待核和风险节点。
- 已实现 `brand_radar_weekly`、专用证据链校验和 `--weekly / --source-pack / --require-api`。
- weekly 入口只注册本地只读工具，结果强制 `external_actions=[]` 与 `awaiting_human_review`。
- 四个固定证据预处理阶段为 `read_weekly_settings`、`read_weekly_source_pack`、`resolve_weekly_versions`、`merge_weekly_events`。
- 当前 1.1 调查白名单为 `inspect_local_evidence`、`compare_event_versions`、`compare_competitor_evidence`、`cross_check_conflicting_evidence`，模型一次选择 1–4 个动作。
- 当前 1.1 默认真实周报主演示成功：`outputs/brand_radar_weekly-real-20260901-095856-333379.json` 与同名 HTML，真实 `deepseek-v4-flash`，30.4 秒，3 个调查动作、首轮生成即通过、7 张情报卡、3 条 Brief，`awaiting_human_review`，`external_actions=[]`。此前 `004131` 只作为旧证据保留。
- 库迪目标变体成功：`outputs/brand_radar_weekly-real-20260901-001559-688407.json` 与同名 HTML，路径转向库迪缺证与快闪关联，并生成缺证卡供人工复核。
- 错误 Key 已验证：0.7 秒退出码 3，明确失败，无新增 JSON / HTML / tmp，无 Mock。
- 当前测试数为 73。
- 17:50 左右程序合成 `adjustment_reasons` 的文件不得作为真实 Agent 证据或 Dashboard 输入。

## 已知事实

- `run.py` 是当前 CLI 入口，现有命令 `python3 run.py --help` 和 `python3 run.py --list` 可作为基线检查。
- `framework/llm_client.py` 支持 OpenAI、Anthropic、DeepSeek、Moonshot 和 Zhipu；weekly 的 `--require-api` 会禁止缺 Key 或请求失败时进入 Mock。
- `framework/agent_runner.py` 已有场景识别、工具调用、轮次限制、重复调用保护、1.1 计划 / 调查 / 修正闭环和结构化输出解析。
- `framework/scenario_registry.json` 仍保留早期多场景配置，但 `brand_radar_weekly` 只注册四个本地只读阶段，不注册飞书或其他外部写入工具。
- 咖啡 Replay 包、`brand_radar_weekly`、专用结果校验、真实 Key 合格产物和本地 HTML 周会稿均已具备；交互 Dashboard / chat 尚未实现，下一阶段按用户使用价值决定是否做。

当前唯一 canonical 交付物是通过专用校验后原子保存的 JSON。JSON 与 HTML 共用一份由已校验情报卡 priority 生成的人话摘要，不保存无卡片支撑的模型草稿句；模型判断仍可从卡片、Brief、调查动作和工具反馈追溯。HTML 周会稿、未来 Dashboard、未来报告和可能的 chat 解释入口都必须读取同一份 artifact；当前 CLI 没有 GUI chat、交互 Dashboard、自动刷新或实时抓取。首页按 priority 稳定生成“本周优先讨论 / 信息不够先别拿进方案 / 明确不采用 / 继续观察”的人话结论，并优先露出待核卡。

## Mac Mini 下一项任务

下一项最小产品工作是基于 73 项测试和 `095856` 主演示做 postflight 收尾，补充一批更接近真实企划的消费、竞品和内容素材，让 Brief 从“方向雏形”升级到可直接进入创意会的版本；再根据使用反馈决定是否增加交互 Dashboard / chat。不要为了形式迁移 Dify，也不要先做复杂框架或旧目录迁移。

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

验收通过时应显示真实 Provider、模型、材料包、JSON 输出位置、HTML 周会稿位置和人工复核提示。主动去掉 `--require-api` 且缺 Key 时，才允许进入清楚标记的 Mock 烟雾测试。

## 原始案例参考边界

只把 RealReplicaBench 当成工作方法来源，不复制任务文案、数据、代码、业务对象或交付物。参考固定版本：

- `https://github.com/Accio-Lab/RealReplicaBench/tree/4041872837eb960a16bbe3d73b459f20680b8ad6`

重点吸收的方法是：从问题到可信洞察、让来源与结论相连、从信号到行动建议、面向周会组织简报、先读完整材料、还原最新有效版本、排除旧通知和无关项、草稿不是事实源、对外动作前停在人审。不要复制外部产品，也不要堆平台。

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
