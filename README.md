# Brand Radar

面向营销企划人员的品类营销情报 Agent。用户给出品牌、品类、地区和关注方向，系统提出竞品观察名单，聚合公开营销信号，完成去重、聚类、筛选与排序，并通过营销 Dashboard 输出统一情报流、营销日历、新兴关键词和可追溯的 Brief 角度。

> **项目状态（2026-08-31）**：仓库当前代码是 V4.2 多场景 Agent 工程基线；聚焦后的 Brand Radar Dashboard MVP 已完成产品契约并进入执行准备，尚未实现。Replay、Mock 或 Synthetic 内容必须明确标识，不能视为实时情报或业务效果证据。

## 聚焦案例

首个可复跑案例固定为：

- 种子品牌：瑞幸咖啡
- 品类：现制咖啡 / 连锁咖啡
- 地区：全国 + 上海
- 观察窗口：过去 7 天 + 未来 30 天
- 关注方向：竞品 Campaign、产品与联名、节日节点、地区活动、突发热点、新兴关键词、敏感纪念日

目标使用路径：

```text
配置品牌观察面
  → Agent 提出竞品候选并由用户确认
  → 聚合公开营销信号
  → 去重、聚类、筛选、排序
  → 浏览统一情报流 / 日历 / 关键词 / Brief
  → 查看来源、关注、忽略或继续加工
```

## 当前真实能力

### 代码中已有

- Python CLI 统一入口与自然语言场景路由。
- OpenAI、Anthropic、DeepSeek、Moonshot、智谱 Provider 适配。
- 有限轮次的工具调用、重复调用保护和 MockProvider 回退。
- Pydantic 结构化输出：观察 → 洞察 → 决策点 → 建议，并保留 evidence references。
- Google Trends、Hacker News、公开微博聚合源和公开 URL 读取适配器。
- 本地运行记录与经验归档原型。

### 已定义、尚未实现

- BrandProfile 与可确认的竞品观察名单。
- `SourceDocument → MarketingSignal → SignalCluster → BriefSuggestion → Feedback` 数据链。
- 跨来源去重、Campaign 聚类、相关性与新颖性排序。
- 营销 Dashboard、未来 30 天日历、新兴关键词和三个 Brief 角度。
- 敏感日期、来源冲突、单源待核和人工确认状态。
- 固定瑞幸 Replay 数据、bad-case 回归集、MVP 端到端测试。

详细边界见 [项目状态](docs/PROJECT-STATE.md)。

## 文档入口

|文档|回答的问题|
|---|---|
|[MVP 产品契约](docs/product/PRD.md)|产品为谁解决什么问题，第一圈做到哪里|
|[产品迭代计划](docs/product/ROADMAP.md)|产品能力按什么顺序形成 P0–P4|
|[Agent 执行目标](docs/AGENT-EXECUTION-GOAL.md)|产品内 Agent 与工程执行 Agent 分别必须完成什么|
|[作品集证据契约](docs/PORTFOLIO-EVIDENCE.md)|什么证据可以公开展示，什么表述必须等待验收|
|[当前项目状态](docs/PROJECT-STATE.md)|已核实能力、未完成项、风险和下一步|
|[Mac Mini handoff](docs/handoff/2026-08-31-macmini-bootstrap.md)|下一台机器如何克隆、启动、验收并继续|

Mac Mini 或新 Agent 的默认读取顺序：`README → PROJECT-STATE → PRD → ROADMAP → AGENT-EXECUTION-GOAL → 最新 handoff`。

## 运行现有 V4.2 基线

现有命令用于验证旧 CLI 工程基线，不代表聚焦后的 Dashboard MVP 已经完成。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt

# 无 API Key 时使用 MockProvider
python3 run.py --list
```

不要提交 `.env`。Live Provider 的 API Key 必须在每台机器上单独配置。自然语言任务可能访问网络、写入运行状态，若配置 webhook 还可能外发；它不是首次环境 smoke 命令。

## 数据与证据规则

- `LIVE`：来自本次运行实际访问的公开来源，保留 URL、发布时间和抓取时间。
- `REPLAY`：固定公开样例，用于演示、测试和回归。
- `MANUAL`：用户提供的公开 URL 或授权数据。
- `SYNTHETIC`：仅用于明确标注的界面或结构样例。

Live 来源失败时必须显示失败状态，不能使用 Replay 或 Synthetic 数据补成实时结论。小红书、抖音等平台只接公开可访问页面、用户提供 URL 或授权数据，不绕过登录或平台限制。

## Agent 行为原则

- 角色是营销情报编辑，不是客服聊天助手。
- 先筛选和降噪，再生成摘要；同一 Campaign 的重复材料合并呈现。
- 事实、推断与建议分层；结论只能引用实际存在的来源或 Signal ID。
- 默认表达顺序：结论 → 为什么是现在 → 证据 → 机会角度 → 风险与未知。
- 高风险敏感日期、来源冲突或证据不足时进入人工确认，不为凑齐 Brief 绕过风险。
- Prompt、工具说明、排序规则和输出 Schema 必须版本化并可回放。

## 公开作品边界

当前可以证明：已有多模型、工具调用、结构化输出和 Mock/Live 分层的营销 Agent 工程原型；已完成聚焦 Dashboard 的产品契约、执行目标和跨设备交接设计。

当前不能声称：Dashboard 已上线、已完成全网实时监测、已稳定抓取小红书/抖音、已替代人工、实现固定效率提升或被真实品牌生产采用。

后续简历或案例升级必须以可运行 Replay、真实来源记录、界面截图、bad-case 回归和可复核 commit 为证据。参见 [作品集证据契约](docs/PORTFOLIO-EVIDENCE.md)。

## 安全与贡献约束

- 禁止强推默认分支；`push_v4.sh` 已停用，仅保留历史说明。
- 不提交密钥、Cookie、浏览器配置、运行数据库、`.venv`、缓存或本地日志。
- 不把 Mock、Replay、估算工时或界面文案包装成真实运行结果。
- 外部发布、自动发稿、投放和法律结论不在 MVP 范围内。
- 第三方 Agent 壳可以依法依 License 复用，但必须保留必要声明，不得包装为自研框架。

## 许可证状态

仓库目前没有独立 `LICENSE` 文件。确定开源许可前，请不要仅依据历史 README 文案推断授权范围；第三方依赖分别遵循其自身 License。
