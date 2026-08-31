# 当前状态

更新日期：2026-08-31

## 当前结论

产品方向已经收敛为“下周营销企划情报 Agent”：真实模型 API Key 驱动完整工作流，Replay / 公开材料提供可复查输入，Dashboard 展示同一次 Agent 结果并承接人工复核。

Day 1–2 的可运行 CLI 骨架已在目标提交 `08704a00e2e3105934b4345154babbd91ff67a4a` 之上实现并通过“真能跑”验收：咖啡 Replay 包、`brand_radar_weekly`、专用结果校验、严格 API 开关、错误 Key 失败路径、真实 DeepSeek 结果和关键词变化证据均已取得。当前阶段按约定停在人工复核前，不包含任何外部执行动作。

这不能称为完整 Brand Radar Agent Demo。当前是代码原生的受约束单 Agent 工作流，不是 Dify；四个前置工具仍由程序固定执行，模型没有真实形成调查计划或选择下一步，校验失败后也没有最多一次的受限修正。V1 不通过迁移 Dify 或增加多 Agent 来掩盖这个缺口。

## 2026-08-31 实现证据

- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`：33/33 通过。
- Mock 周企划生成 7 张情报卡和 3 条 Brief，结果明确标记为 Mock，并停在 `awaiting_human_review`。
- 缺 Key + `--require-api`：退出码 2，在读取材料前停止。
- 故意错误的 DeepSeek Key + `--require-api`：退出码 3，明确报告鉴权失败，不降级 Mock、不生成结果，运行前后输出文件集合不变。
- 真实 DeepSeek Key + `deepseek-v4-flash`：默认观察包在 21.9 秒内生成通过专用校验的 real JSON，包含 7 张情报卡、3 条不同视角 Brief，状态为 `awaiting_human_review` 且 `external_actions=[]`。
- 关键词变体：只把输入设置从 `社区空间` 改为 `早餐通勤` 后再次真实运行；模型没有把无材料支撑的早餐词写成结论，原有社区空间关键词及相关竞品引用消失，结果仍通过同一校验。
- 本机验收产物位于已忽略的 `outputs/brand_radar_weekly-real-20260831-154021-446362.json` 和关键词变体结果；运行输出不提交 Git。
- 人工逐卡复核确认 7 张卡没有捏造材料中不存在的经营数字，并对合作关系、客流和未核快闪保留了限制说明；但“中秋国庆竞品空位”Brief 仍只有节假日日历与星巴克社区空间卡，缺少竞品节日动作的直接证据。结果已把该证据列为 missing_evidence，这也说明图引用合法不等于营销调查充分，完整 Agent Demo 仍需下一道硬门。

## 已确认可复用资产

- `run.py`：现有 Python CLI 入口。
- `framework/llm_client.py`：OpenAI、Anthropic、DeepSeek、Moonshot、Zhipu 接入和 Mock 回退。
- `framework/agent_runner.py`：场景路由、工具执行、轮次限制、重复调用保护、上下文与运行记录。
- `framework/output_schema.py`：事实、洞察和建议的引用校验基础。
- `v3_agent/tools.py`：早期工具定义和本地示例数据。
- `scenarios/tools_real.py`：Google Trends、Hacker News、微博聚合和公开网页读取的早期尝试。

Day 1–2 已在这些基础上新增咖啡观察包、单场景运行时和专用结果校验。尚未完成的是 Dashboard、三分钟人工复核路径和下一阶段的页面验收。

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

- “真像营销 Agent”硬门：目标驱动的调查计划、白名单工具选择、工具反馈后的判断调整，以及校验失败后的最多一次修正。
- 关键词之外的竞品或矛盾材料变化测试，并验证调查路径而不只是最终文案发生合理变化。
- 读取同一结果的 Dashboard 和人工采用 / 退回 / 补证操作。
- 页面截图和三分钟业务验收。
- 断网等下一阶段异常路径的真实环境证据；缺 Key、错误 Key、材料缺失和无效引用已有 CLI 或自动化测试覆盖。

## 已知代码偏差

- 旧 CLI 场景仍保留麦当劳示例、早期外部工具与飞书工具；weekly 入口已隔离且不注册这些工具，物理迁移继续延后。
- `requirements.txt` 仍包含旧实时工具依赖；本轮只在 `.venv` 安装 weekly 必需的核心依赖，没有为目录整理拆分依赖文件。
- 当前专用校验能保证来源存在、版本合并、引用图和安全边界，但不能单靠代码判断一张合法引用的卡是否足以支持营销角度；下一闭环要通过受限对比动作和 missing_evidence 反馈补这一层。
- 智谱尝试曾遇到 `glm-4.7-flash` 平台错误码 `1305`；它是历史环境记录，不再阻塞当前已通过的 DeepSeek 路径。

## 仓库整理决定

- 本轮只整理 README、业务文档、开发入口和忽略规则。
- Mac Mini 交接说明已放在 `docs/handoff/MACMINI-HANDOFF.md`，并会同步到 `/private/tmp/brand-radar-macmini-business-handoff.md` 供本机直接转交。
- 暂不物理移动 `run.py`、`framework/`、`v3_agent/tools.py`、`scenarios/tools_real.py`，避免在新入口出现前破坏现有 CLI。
- `v1_basic/`、`v2_structured/`、`v3_agent/agent.py` 和旧场景作为早期探索保留，但不再出现在默认产品路径。
- 新运行结果放入已忽略的 `outputs/`，不得提交 API Key 或本机状态。
- weekly 新入口已通过真实 API；仍等 Dashboard 和人工路径完成后，再单独决定 legacy 物理迁移。

## 下一项最小工作

Day 1–2 到此停止。下一阶段若由用户明确启动，先实现最小有界闭环：“目标 → 观察 → Agent 计划 / 白名单工具选择 → 工具反馈 → 生成 → 专用校验 → 最多一次修正 → 人工复核”。通过这道 Agent 性验收门后，再让轻量 Dashboard 读取同一份结果；不先做 Dify 迁移、实时抓取、多 Agent、数据库、账号系统或目录迁移。
