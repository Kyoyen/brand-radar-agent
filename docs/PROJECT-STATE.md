# 当前状态

更新日期：2026-08-31

## 当前结论

产品方向已经收敛为“下周营销企划情报 Agent”：真实模型 API Key 驱动完整工作流，Replay / 公开材料提供可复查输入，Dashboard 展示同一次 Agent 结果并承接人工复核。

本轮完成的是业务主线与仓库入口整理，没有把文档完成写成代码完成。第一版业务链仍需在 Mac Mini 上实现和实跑。

## 已确认可复用资产

- `run.py`：现有 Python CLI 入口。
- `framework/llm_client.py`：OpenAI、Anthropic、DeepSeek、Moonshot、Zhipu 接入和 Mock 回退。
- `framework/agent_runner.py`：场景路由、工具执行、轮次限制、重复调用保护、上下文与运行记录。
- `framework/output_schema.py`：事实、洞察和建议的引用校验基础。
- `v3_agent/tools.py`：早期工具定义和本地示例数据。
- `scenarios/tools_real.py`：Google Trends、Hacker News、微博聚合和公开网页读取的早期尝试。

这些资产只证明存在可复用基础。当前仓库没有真实 Key 的 Brand Radar 默认场景验收记录，也没有完成瑞幸观察包、专用结果、Dashboard 或三分钟人工路径。

## 当前文档事实源

开发按以下顺序读取：

1. `README.md`
2. `docs/product/PRD.md`
3. `docs/business/NEXT-WEEK-WORKFLOW.md`
4. `docs/product/AGENT-BUILD.md`
5. `docs/product/ROADMAP.md`
6. `docs/PROJECT-STATE.md`
7. `docs/handoff/MACMINI-HANDOFF.md`

旧根目录规划稿、历史对话和 V1-V3 示例不能覆盖这条当前主线。

## 外部参考事实源

业务流程只以阿里国际 Accio 团队维护的 RealReplicaBench 官方原始仓库和固定版本 `4041872837eb960a16bbe3d73b459f20680b8ad6` 为参考事实源。

本项目通过 `fusion` 只吸收最新有效指令、跨材料核对、先读当前状态、只补缺口、保留证据和人工复核等工作原则。瑞幸场景、周度观察包、四类企划结果和人工决定路径均为 Brand Radar 自己的方案。

## 尚未完成

- 咖啡品类 Replay 观察包及人工期望结果。
- `brand_radar_weekly` 当前场景与只读业务工具。
- 真实模型必需模式及明确失败处理。
- Brand Radar 专用情报卡、日历、关键词、Brief 和运行信息校验。
- CLI 端到端真实 API 运行。
- 读取同一结果的 Dashboard 和人工采用 / 退回 / 补证操作。
- 页面截图、三分钟业务验收和异常路径证据。

## 已知代码偏差

- 缺 API Key 时当前代码会自动降级为 Mock，不满足真实模式验收的明确失败要求。
- 默认 Prompt 和示例数据仍以麦当劳等早期案例为主。
- 场景注册表包含未注册工具名称和自动飞书推送意图，不适合作为第一版默认流程。
- 通用输出还不能完整表达情报卡、版本取舍、日历、关键词、Brief 引用和待核项。
- 早期“真实工具”依赖外部公开服务，稳定性和数据边界尚未经过本场景验证。

## 仓库整理决定

- 本轮只整理 README、业务文档、开发入口和忽略规则。
- Mac Mini 交接说明已放在 `docs/handoff/MACMINI-HANDOFF.md`，并会同步到 `/private/tmp/brand-radar-macmini-business-handoff.md` 供本机直接转交。
- 暂不物理移动 `run.py`、`framework/`、`v3_agent/tools.py`、`scenarios/tools_real.py`，避免在新入口出现前破坏现有 CLI。
- `v1_basic/`、`v2_structured/`、`v3_agent/agent.py` 和旧场景作为早期探索保留，但不再出现在默认产品路径。
- 新运行结果放入已忽略的 `outputs/`，不得提交 API Key 或本机状态。
- 新入口完成并通过真实 API 与 Dashboard 验收后，再单独决定 legacy 物理迁移。

## Mac Mini 的第一项开发工作

先完成开发计划第一、二天：准备来源与版本齐全的 Replay 观察包，然后用最小代码改动打通 `brand_radar_weekly` 的真实 API 全流程。此时只需 CLI 结果和引用校验，不先做实时抓取，也不先迁移旧目录。
