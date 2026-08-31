# Brand Radar MVP PRD

更新日期：2026-08-31

状态：产品方向已确认，进入工程执行准备

聚焦案例：瑞幸咖啡 / 现制咖啡品类 / 全国 + 上海

## 1. 产品定义

Brand Radar 是面向营销企划人员的品类营销情报 Agent。用户输入品牌、品类、地区和关注方向后，系统提出同品类竞品观察名单，聚合公开营销信号，经过去重、聚类、筛选和排序后，在 Dashboard 中输出统一情报流、营销日历、新兴关键词和可追溯的 Brief 角度。

它交付的是经过编辑判断的“今天值得看什么”，不是新闻搜索结果或社媒链接堆积。

## 2. 用户与问题

主要用户是品牌市场、营销企划、内容策划和 Campaign Planner。他们需要在短时间内完成案头研究，并把情报转化成选题、Brief 或内部讨论材料。

核心痛点：

- 信息入口分散，人工复制整理成本高。
- 竞品动作、节日节点、地区活动、平台热点和敏感日期缺少同一张企划视图。
- 原始链接不能直接回答“为什么现在值得看”和“下一步可以做什么”。
- 模型容易把低证据信息写成事实，把普通热度误判为营销机会。

## 3. 默认案例

| 配置项 | 默认值 |
| --- | --- |
| 种子品牌 | 瑞幸咖啡 |
| 品类 | 现制咖啡 / 连锁咖啡 |
| 地区 | 全国 + 上海 |
| 观察窗口 | 过去 7 天 + 未来 30 天 |
| 关注方向 | 竞品 Campaign、产品与联名、节日节点、地区活动、突发热点、新兴关键词、敏感纪念日 |
| 数据模式 | Replay first，可扩展 Live public |

系统可以提出星巴克中国、库迪咖啡、Manner、麦咖啡等候选观察对象，但候选名单必须有理由，并由用户确认后进入正式监测。

## 4. 最小价值闭环

```text
输入品牌 / 品类 / 地区 / 关注方向
  -> Agent 提出竞品观察名单
  -> 用户确认
  -> 采集公开营销信号
  -> 标准化、去重、聚类、筛选、排序
  -> 统一情报流 + 营销日历 + 新兴关键词 + Brief 建议
  -> 筛选 / 查看证据 / 生成 Brief / 标记关注或忽略
```

MVP 的最小圆环以“一次可复跑的刷新”成立：配置观察面、确认竞品、生成 Dashboard、打开证据、得到一个 Brief 角度。自动定时运行、跨团队协作和完整舆情监测都不作为第一圈前提。

## 5. 营销信号范围

所有内容先进入统一的 `MarketingSignal`，再通过多标签筛选。

- 品牌与竞品：新品、联名、促销、价格动作、会员玩法、创意物料、门店动作、线上 Campaign。
- 时间节点：法定节假日、消费节、季节节点、品牌自定义节点、敏感纪念日和不宜娱乐化表达的日期。
- 地区活动：商圈、市集、展览、赛事、校园、文旅和城市级事件。
- 突发热点：社会热点、流行梗、娱乐或体育事件及其品牌跟进情况。
- 内容与平台趋势：公开可访问的小红书讨论、抖音趋势、搜索趋势、营销媒体文章和新兴关键词。
- 约束信号：广告、食品、促销、未成年人、代言和地域表达等公开政策或风险提示。

## 6. Dashboard 信息架构

Dashboard 是产品主形态，搜索框只是入口之一。

- 全局观察栏：品牌、品类、地区、时间窗口、竞品名单、Replay / Live 状态和刷新时间。
- 统一情报流：默认按“值得关注程度”排序，可切换最新、即将发生或风险优先。
- 营销日历：未来 30 天节日、消费节点、地区活动、品牌动作和敏感纪念日。
- 新兴关键词：展示近期新出现、增速明显或跨来源共现的词。
- Brief 建议：给出 3 个优先角度，每个角度引用相关 Signal 或 Cluster。

视觉方向是营销编辑部 / Brand Studio 风格：信息密度接近 AI HOT，但页面气质更偏营销企划工作台，减少工程控制台感。

## 7. Agent 行为契约

Agent 的角色是资深营销情报编辑和企划助理。它负责缩小注意力范围、补齐上下文、提出可执行角度；最终品牌判断仍由人完成。

每次运行必须执行：

- 判断来源是否与当前品牌、品类、地区和观察窗口相关。
- 合并重复报道和同一 Campaign 的不同表达。
- 区分事实、媒体解释、平台热度和模型推断。
- 依据新颖性、时效、相关性、影响范围、证据质量和风险排序。
- 单一低可信来源标记为待核，不得补写成确定事实。
- 给出“为什么现在值得看”和下一步 Brief 角度。
- 敏感日期、来源冲突或高风险信号触发人工确认。

语言规范：

- 先说结论，再说为什么是现在、证据、机会角度、风险与未知。
- 使用营销团队能直接转述的短句。
- 不使用“亲爱的 KFCer”“尊敬的用户”“已为您全网扫描”等客服腔或拟人化套话。
- 推荐开场：`今天新增 8 个值得关注的营销信号，优先看这 3 个。`

## 8. 数据契约

最小领域链路：

```text
BrandProfile -> SourceDocument -> MarketingSignal -> SignalCluster -> BriefSuggestion -> Feedback
```

字段基线：

```text
BrandProfile
  brand, category, regions, audience, watch_topics,
  competitor_watchlist, past_window, future_window

SourceDocument
  id, url, source_name, source_type, title,
  published_at, fetched_at, excerpt, data_mode

MarketingSignal
  id, source_ids, brands, event_type, regions,
  event_date, facts, keywords, novelty, relevance, risk_tags

SignalCluster
  id, signal_ids, canonical_title, source_count,
  summary, why_now, confidence, contradictions, missing_evidence

BriefSuggestion
  id, cluster_ids, opportunity, evidence,
  direction, risk_and_unknowns, human_review_required

Feedback
  target_id, action, note, created_at
```

事实、推断和建议必须分层呈现。模型生成的结论只能引用真实存在的 Source、Signal 或 Cluster ID。

## 9. MVP 范围

Must:

- 创建或修改一个 `BrandProfile`。
- 自动提出竞品候选并由用户确认观察名单。
- Replay 数据跑通采集后的标准化、去重、聚类、筛选和排序。
- Dashboard 展示统一情报流、营销日历、新兴关键词和 3 个 Brief 角度。
- 每条判断可回到来源，Live / Replay 清楚区分。
- 关键词、品牌、地区、节点和风险筛选实时影响情报流。
- Agent System Prompt、结构化输出和至少一组 bad-case 回归样例可版本化。

Should:

- 至少一个可稳定访问的 Live public 来源刷新。
- `关注 / 忽略 / 生成 Brief` 状态可保存，并影响下一轮排序。
- 公开创意物料缩略图和信号详情抽屉。
- 一键切换全国与单一城市观察面。

Won't:

- 绕过登录、风控或平台限制的灰色爬虫。
- 自动生成后直接发布内容、自动投放或替代法务判断。
- Agent 自主修改自身代码和规则。
- 为展示“智能”而堆叠多个无必要的 Agent、角色或场景页。

## 10. 验收标准

- 无密钥可运行固定瑞幸 Replay 案例，页面全程显示 `REPLAY`。
- 固定样例包含不少于 15 条原始公开材料、3 类来源和多个重复报道。
- 处理后形成 5-10 个非重复 Signal Cluster。
- 同一 Campaign 的重复材料只占一张主卡。
- 低相关高热度内容被降权并解释原因。
- 每张卡均可看到来源 URL、发布时间、抓取时间、数据模式和证据缺口。
- 营销日历可查看未来 30 天，并区分节日、地区活动、品牌动作和敏感纪念日。
- 高风险敏感日期与促销方向冲突时，对应 Brief 被暂停并说明原因。
- 新兴关键词面板至少展示 10 个可点击词。
- 3 个 Brief 角度均引用已存在的 Signal 或 Cluster。
- 新用户在 3 分钟内完成“确认观察面 -> 找到优先信号 -> 查看证据 -> 生成 Brief 角度”。

这些指标用于验收固定演示，不对每天波动的 Live 数据强行规定信号数量。
