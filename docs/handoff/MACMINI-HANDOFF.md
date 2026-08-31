# Mac Mini 交接说明

更新日期：2026-08-31

## 交接结论

本仓库已完成第一版业务主线和文档入口整理。当前还不是可验收的 Brand Radar Agent；Mac Mini 的任务是把文档里的单一业务链落成真实 API Key 可跑通的 CLI Agent，再接 Dashboard。

第一版目标只做一件事：使用真实模型 API Key 读取咖啡品类 Replay / 人工补充材料，输出下周企划会需要的情报流、30 天日历、重点关键词和 3 条 Brief，并停在人工复核前。

## 开始前先读

按顺序阅读：

1. `README.md`
2. `docs/product/PRD.md`
3. `docs/business/NEXT-WEEK-WORKFLOW.md`
4. `docs/product/AGENT-BUILD.md`
5. `docs/product/ROADMAP.md`
6. `docs/PROJECT-STATE.md`

这些文件是当前事实源。历史对话、旧根目录规划稿、V1-V3 示例和 Mock 输出不能覆盖这条主线。

## 已完成

- README 已改成业务入口，说明 V1 必须真实 API Key 跑完整 Agent 流程。
- PRD 已改成营销企划业务流程语言，包含材料、判断、交付和验收。
- 新增 `docs/business/NEXT-WEEK-WORKFLOW.md`，用 `fusion` 从 Accio / RealReplicaBench 原始任务提炼可迁移工作方法，并转译成 Brand Radar 自有流程。
- 新增 `docs/product/AGENT-BUILD.md`，保留“怎么打造 Agent”的工程说明。
- Roadmap 和 Project State 已改成 Mac Mini 可以直接接续的五天计划与缺口清单。
- `.env.example` 已明确 Mock 只用于烟雾测试；`.gitignore` 已忽略 `.env`、`outputs/`、`memory/` 和本地日志。

## 已知事实

- `run.py` 是当前 CLI 入口，现有命令 `python3 run.py --help` 和 `python3 run.py --list` 可作为基线检查。
- `framework/llm_client.py` 支持 OpenAI、Anthropic、DeepSeek、Moonshot 和 Zhipu，但缺 Key 会自动进入 Mock；V1 需要增加 `--require-api` 之类的验收开关。
- `framework/agent_runner.py` 已有场景识别、工具调用、轮次限制、重复调用保护和结构化输出解析。
- `framework/scenario_registry.json` 仍是早期多场景配置，包含自动飞书推送意图和未注册工具名，不适合作为 V1 默认入口。
- 当前尚无咖啡品类 Replay 观察包、`brand_radar_weekly` 场景、专用结果校验、Dashboard、真实 Key 端到端运行证据。

## Mac Mini 第一项任务

先做开发计划第一、二天，不先迁移旧目录，不先做实时抓取，不引入多 Agent、数据库、账号或调度。

实现范围：

- 新建 `data/replay/coffee-week-2026-09-07/manifest.json` 和 `sources/`，每份材料包含来源、日期、链接或文件位置、来源类型和版本线索。
- Replay 包至少包含一组重复事件、一组新旧版本、一项无关或过期内容、一项待核内容和一个风险节点。
- 新增 `scenarios/brand_radar_weekly.py`，只读本次观察包，完成读取、版本核对、事件合并、优先级判断、日历、关键词和 Brief 生成。
- 新增 Brand Radar 专用输出校验：卡片 ID 唯一、来源存在、Brief 引用有效、日期格式正确、来源类型明确、外发动作为空。
- 在 `run.py` 增加周企划入口和真实模型必需模式。缺 Key、错误 Key、网络失败或模型异常时必须清楚失败，不能静默降级 Mock。
- 输出写入 `outputs/`，该目录不提交 Git。Dashboard 后续必须读取同一份结果，不能另写静态结论。

## 目标命令

当前命令可用于基线检查：

```bash
python3 run.py --help
python3 run.py --list
```

实现完成后应支持：

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
- 不移动 `run.py`、`framework/`、`v3_agent/tools.py`、`scenarios/tools_real.py`，直到新入口跑通且回归命令更新。
- 不自动发送飞书、发稿、投放、改预算或调用任何外部写入动作。
