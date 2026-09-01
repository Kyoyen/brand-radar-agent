# 当前状态

更新日期：2026-08-31

## 当前结论

产品方向已经收敛为“下周营销企划情报 Agent”：真实模型 API Key 驱动完整工作流，Replay / 公开材料提供可复查输入，校验通过后原子保存的 JSON 作为唯一 canonical 结果，本地 HTML 周会稿从同一份 JSON 自动生成，交互 Dashboard / chat 后续只作为候选入口承接人工复核。

Day 1–2 的可运行周会骨架已在目标提交 `08704a00e2e3105934b4345154babbd91ff67a4a` 之上继续实现：咖啡 Replay 包、`brand_radar_weekly`、专用结果校验、严格 API 开关、错误 Key 失败路径、人工复核边界和同源 HTML 周会稿均已落到当前工作树。

验收状态需要分层记录：历史 `schema_version=1.0` 骨架曾用真实 DeepSeek Key 通过“真能跑”；当前 `schema_version=1.1` 工作树已用 DeepSeek `deepseek-v4-flash` 跑通默认周报和库迪目标变体，并验证错误 Key 明确失败、不降级 Mock、不留下新产物。当前可以称为 Day 1–2 可运行骨架通过，但不能称为完整成熟 Brand Radar Agent。

当前是代码原生的受约束单 Agent 工作流，不是 Dify。四个固定证据预处理阶段仍由程序执行；模型负责记录调查计划并从本地白名单选择 1–4 个动作，读取反馈后再生成。V1 不通过迁移 Dify、堆平台或增加多 Agent 来制造复杂感。

## 2026-09-01 实现证据

- 当前测试数为 73。
- 主演示默认真实周报：`outputs/brand_radar_weekly-real-20260901-095856-333379.json` 与同名 `.html`，`schema_version=1.1`，real / deepseek / `deepseek-v4-flash`，30.4 秒，3 个调查动作，首轮生成即通过，7 张情报卡，3 条 Brief，`awaiting_human_review`，`external_actions=[]`。
- 旧证据默认真实周报：此前 `004131` 可保留为旧成功证据，但不再作为当前主证据。
- 库迪目标变体：`outputs/brand_radar_weekly-real-20260901-001559-688407.json` 与同名 `.html`，调查路径转向库迪缺证与快闪关联，生成库迪缺证卡，Brief 和人工复核项能正确引用。
- 错误 Key：0.7 秒退出码 3，明确鉴权失败，无新增 JSON / HTML / tmp，无 Mock。
- HTML 周会稿：从同一 JSON 自动生成，展示本周重点、3 条 Brief、未来 30 天关键节点、关键词、Agent 为何调查、来源和人工复核。首页按卡片 priority 稳定生成“本周优先讨论 / 信息不够先别拿进方案 / 明确不采用 / 继续观察”的人话结论，并优先露出待核卡；不要再把一句模型摘要措辞当作整份周报失败。
- JSON 与 HTML 共用由已校验情报卡 priority 生成的稳定摘要，不保存无卡片支撑的模型草稿句；模型判断仍从卡片、Brief、调查动作和工具反馈追溯。
- Mock 周企划仍只用于未 `--require-api` 且缺 Key 时的程序烟雾测试，结果必须明确标记。
- 缺 Key + `--require-api` 历史证据：退出码 2，在读取材料前停止。
- 17:50 左右出现过由程序合成 `adjustment_reasons` 的文件；该文件不是 Agent 读取工具反馈后的真实产物，不得作为验收证据或 Dashboard 输入。

## 已确认可复用资产

- `run.py`：现有 Python CLI 入口。
- `framework/llm_client.py`：OpenAI、Anthropic、DeepSeek、Moonshot、Zhipu 接入和 Mock 回退。
- `framework/agent_runner.py`：场景路由、工具执行、轮次限制、重复调用保护、上下文与运行记录。
- `framework/output_schema.py`：事实、洞察和建议的引用校验基础。
- `v3_agent/tools.py`：早期工具定义和本地示例数据。
- `scenarios/tools_real.py`：Google Trends、Hacker News、微博聚合和公开网页读取的早期尝试。

Day 1–2 已在这些基础上新增咖啡观察包、单场景运行时、专用结果校验、1.1 调查轨迹和本地 HTML 周会稿。尚未完成的是三分钟人工复核路径、交互 Dashboard / chat 取舍、图像素材来源治理和更丰富的页面验收。

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

本项目通过 `fusion` 只吸收最新有效指令、跨材料核对、先读当前状态、只补缺口、保留证据、从问题到可信洞察、来源与结论相连、从信号到行动建议、面向周会简报和人工复核等工作原则。瑞幸场景、周度观察包、四类企划结果、HTML 周会稿和人工决定路径均为 Brand Radar 自己的方案。

## 尚未完成

- Brief 仍是企划雏形，需要更丰富材料和业务语言继续打磨，不能当成成熟投放 Brief。
- 来源包没有图像素材，也没有实时抓取；内容增强应优先补可复查公开来源和来源权限。
- “未来 30 天”当前是关键节点，不是逐日内容日历。
- 交互 Dashboard / chat 尚未实现；现在已有本地 HTML 周会稿，下一阶段需判断是否值得增加交互入口。
- 页面截图、三分钟业务验收和人工采用 / 退回 / 补证操作。
- 断网等下一阶段异常路径的真实环境证据；缺 Key、错误 Key、材料缺失和无效引用已有 CLI 或自动化测试覆盖。

## 已知代码偏差

- 旧 CLI 场景仍保留麦当劳示例、早期外部工具与飞书工具；weekly 入口已隔离且不注册这些工具，物理迁移继续延后。
- `requirements.txt` 仍包含旧实时工具依赖；本轮只在 `.venv` 安装 weekly 必需的核心依赖，没有为目录整理拆分依赖文件。
- 当前专用校验能保证来源存在、版本合并、引用图和安全边界，但不能单靠代码判断一张合法引用的卡是否足以支持成熟营销角度；这需要人工复核和更丰富来源包继续补。
- 智谱尝试曾遇到 `glm-4.7-flash` 平台错误码 `1305`；它是历史环境记录，不再阻塞 DeepSeek 作为当前真实验收路径继续复验。
- 当前 CLI 无 GUI chat、自动刷新或实时抓取。内容相关外部信息补充仍应先进入 Replay / PUBLIC / MANUAL 观察包，再被标成候选、实际使用或冲突待核来源。

## 仓库整理决定

- 本轮只整理 README、业务文档、开发入口和忽略规则。
- Mac Mini 交接说明已放在 `docs/handoff/MACMINI-HANDOFF.md`。
- 暂不物理移动 `run.py`、`framework/`、`v3_agent/tools.py`、`scenarios/tools_real.py`，避免在新入口出现前破坏现有 CLI。
- `v1_basic/`、`v2_structured/`、`v3_agent/agent.py` 和旧场景作为早期探索保留，但不再出现在默认产品路径。
- 新运行结果放入已忽略的 `outputs/`，不得提交 API Key 或本机状态。
- 当前工作树有代码、测试和文档变更待提交；不要把仓库描述为 clean。
- weekly 新入口已通过当前 1.1 真实 API；等 HTML 周会稿、交互入口取舍和人工路径完成后，再单独决定 legacy 物理迁移。

## 下一项最小工作

下一项最小产品工作是基于 73 项测试和 `095856` 主演示做 postflight 收尾，补充一批更接近真实企划的消费、竞品和内容素材，让 Brief 从“方向雏形”升级到可直接进入创意会的版本；再根据实际使用反馈决定是否增加交互 Dashboard / chat。不要为了形式迁移 Dify，也不要先做复杂框架或旧目录迁移。
