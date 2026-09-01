# 当前状态

更新日期：2026-09-01

## 当前结论

产品方向已经收敛为“品牌驱动的下周营销企划情报 Agent”：企划人员可以沿用通用 `BRAND.md`，也可以通过六个可跳过的问题形成一份本机定制档案；真实模型再读取 Replay / 公开材料，逐轮选择调查重点和营销能力，最终把品牌取舍、行动过程和企划结果一起放进同源周会稿，并停在人工复核前。

当前已经形成可运行的品牌驱动单 Agent 演示骨架：咖啡 Replay 包、`brand_radar_weekly`、通用 / 定制品牌档案、六问终端向导、三个营销技能、逐轮选择与反馈、专用结果校验、严格 API 开关、错误 Key 失败路径、人工复核边界和同源 HTML 周会稿均已实现。

验收状态需要分层记录：历史结果只保留作兼容证据；当前品牌驱动版本已用 DeepSeek `deepseek-v4-flash` 跑通默认周报，并验证错误 Key 明确失败、不降级 Mock、不留下新产物。当前可以称为可运行的品牌驱动单 Agent 演示骨架，但不能称为完整成熟或自治营销产品。输出格式和逐轮控制细节统一见 `docs/product/AGENT-BUILD.md`。

当前入口仍是终端向导与 CLI，不是 GUI，也不是 Dify。品牌六问已经做成可复用状态机，但还没有接到轻量 GUI / chat；V1 不通过堆平台或增加多 Agent 来制造复杂感。

## 2026-09-01 实现证据

- 当前全量测试数为 100。
- 通用品牌档案：真实运行使用根目录 `BRAND.md`，0 个定制答案；六问可逐题跳过，首次建档全部跳过时不创建本机档案。
- 主演示默认真实周报：`outputs/brand_radar_weekly-real-20260901-115850-982265.json` 与同名 `.html`，DeepSeek `deepseek-v4-flash` 约 29.5 秒完成，包含四轮决策、三个调查动作、7 张情报卡和 3 条不同 Brief，最终等待人工复核且没有外部动作。
- 真实决策路径：先核对未验证的上海咖啡快闪，再处理上海旅游节版本组、读取当前旅游节来源，第四轮停止调查并开始成稿；本轮实际使用信号筛选与 Brief 转译。
- Mock 冒烟：显式空 DeepSeek Key 生成 `outputs/brand_radar_weekly-mock-20260901-115812-076795.{json,html}`，终端清楚标记不能作为真实模型业务验收。
- 错误 Key：约 0.9 秒退出码 3，明确鉴权失败、不降级 Mock，产物总数保持 28，无新增 JSON / HTML / tmp。
- HTML 周会稿：从同一 JSON 自动生成，展示通用 / 定制品牌档案、本次实际使用技能、四轮选择、本周重点、3 条 Brief、未来 30 天关键节点、关键词、来源和人工确认。首页继续按卡片 priority 生成“本周优先讨论 / 信息还不够，先别放进方案 / 明确不采用 / 继续观察”的人话结论。
- 当前 Mac 的手工检查入口是 `/Users/kyoyen/Developer/brandradar/outputs/brand_radar_weekly-real-20260901-115850-982265.html`。HTML 结构检查通过；应用内浏览器阻止本地 `file://` 导航，因此本轮没有完成视觉打开检查。该项属于低风险本机手工验收，不得写成已视觉确认。
- JSON 与 HTML 共用由已校验情报卡 priority 生成的稳定摘要，不保存无卡片支撑的模型草稿句；模型判断仍从卡片、Brief、调查动作和工具反馈追溯。
- Mock 周企划仍只用于未 `--require-api` 且缺 Key 时的程序烟雾测试，结果必须明确标记。
- 缺 Key + `--require-api` 历史证据：退出码 2，在读取材料前停止。
- 17:50 左右出现过由程序合成 `adjustment_reasons` 的文件；该文件不是 Agent 读取工具反馈后的真实产物，不得作为验收证据或 Dashboard 输入。
- 上述 `outputs/` 文件均在本机忽略目录，只是当前验收证据；不会随 Git 跨机器交付，交接机器必须运行命令重新生成。

## 已确认可复用资产

- `run.py`：现有 Python CLI 入口。
- `BRAND.md`：首次使用和未建档时的通用品牌判断起点。
- 品牌建档与营销能力：六问状态机、通用 / 定制档案和信号筛选、品牌契合、Brief 转译均已可复用；具体文件和加载方式见 `docs/product/AGENT-BUILD.md`。
- `framework/llm_client.py`：OpenAI、Anthropic、DeepSeek、Moonshot、Zhipu 接入和 Mock 回退。
- `framework/agent_runner.py`：场景路由、工具执行、轮次限制、重复调用保护、上下文与运行记录。
- `framework/output_schema.py`：事实、洞察和建议的引用校验基础。
- `v3_agent/tools.py`：早期工具定义和本地示例数据。
- `scenarios/tools_real.py`：Google Trends、Hacker News、微博聚合和公开网页读取的早期尝试。

当前已在这些基础上新增咖啡观察包、单场景运行时、专用结果校验、品牌档案、逐轮决策轨迹和本地 HTML 周会稿。尚未完成的是定制品牌档案的真实对比验收、六问 GUI / chat 入口、三分钟人工复核路径、图像素材来源治理和页面视觉验收。

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
- 六问目前只有终端向导，轻量 GUI / chat 尚未实现。
- 真实主演示使用通用 `BRAND.md`；还没有用一份真实定制品牌档案验证品牌取舍如何改变调查路径与 Brief。
- 页面截图、三分钟业务试用和人工采用 / 退回 / 补齐来源操作。
- 断网等下一阶段异常路径的真实环境证据；缺 Key、错误 Key、材料缺失和无效引用已有 CLI 或自动化测试覆盖。

## 已知代码偏差

- 旧 CLI 场景仍保留麦当劳示例、早期外部工具与飞书工具；weekly 入口已隔离且不注册这些工具，物理迁移继续延后。
- `requirements.txt` 仍包含旧实时工具依赖；本轮只在 `.venv` 安装 weekly 必需的核心依赖，没有为目录整理拆分依赖文件。
- 当前专用校验能保证来源存在、版本合并、引用图和安全边界，但不能单靠代码判断一张合法引用的卡是否足以支持成熟营销角度；这需要人工复核和更丰富来源包继续补。
- 智谱尝试曾遇到 `glm-4.7-flash` 平台错误码 `1305`；它是历史环境记录，不再阻塞 DeepSeek 作为当前真实验收路径继续复验。
- 当前终端六问和 CLI 无 GUI chat、自动刷新或实时抓取。内容相关外部信息补充仍应先进入 Replay / PUBLIC / MANUAL 观察包，再被标成候选、实际使用或有冲突、需确认的来源。

## 仓库整理决定

- 本轮只整理 README、业务文档、开发入口和忽略规则。
- Mac Mini 交接说明已放在 `docs/handoff/MACMINI-HANDOFF.md`。
- 暂不物理移动 `run.py`、`framework/`、`v3_agent/tools.py`、`scenarios/tools_real.py`，避免在新入口出现前破坏现有 CLI。
- `v1_basic/`、`v2_structured/`、`v3_agent/agent.py` 和旧场景作为早期探索保留，但不再出现在默认产品路径。
- 新运行结果放入已忽略的 `outputs/`，不得提交 API Key 或本机状态。
- 本机定制档案 `memory/brand/BRAND.md` 和运行结果 `outputs/` 保持忽略；跨机器交付只包含通用档案、代码、测试、文档和重建命令。
- weekly 新入口已通过当前真实 API；等六问轻量交互、定制档案对比和人工路径完成后，再单独决定 legacy 物理迁移。

## 下一项最小工作

下一项最小产品工作是把现有六问状态机接到轻量 GUI / chat，再用一份真实定制品牌档案复跑默认观察包，验证品牌取舍会合理改变调查路径、优先级和 Brief。不要先扩复杂 Dashboard，不要为了形式迁移 Dify，也不要先做旧目录迁移。
