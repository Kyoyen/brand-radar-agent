# Marketing Agent OS — 营销场景 Agent 工作台

## 技能简介

这是一个面向品牌营销团队的多场景 Agent 框架，当前已内置 4 个标准化营销工作流，支持自然语言任务路由、三层上下文记忆与执行菜谱归纳复用。

**覆盖场景：**

| 场景 | 触发词示例 | 预计耗时 | 周节省工时 |
|------|-----------|---------|---------|
| 竞品分析 | 竞品动态、小红书分析、竞争对手 | ~5min | ~4h |
| 内容选题 & Brief | 选题、内容方向、brief、排期 | ~3min | ~3h |
| Campaign 复盘 | 复盘、数据总结、渠道表现 | ~4min | ~2h |
| 热点预警 | 热点、借势、话题跟进 | ~3min | ~3h |

---

## 使用方法

### 1. 环境准备

```bash
cd brand-radar-agent
pip install -r requirements.txt

# 设置环境变量（复制后填入真实密钥）
cp .env.example .env
# 编辑 .env:
#   OPENAI_API_KEY=sk-...
#   TARGET_BRAND=你的品牌名
#   FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/...
```

### 2. 执行任务（推荐方式）

```bash
# 自然语言描述任务，Agent 自动识别场景并执行
python run.py "帮我看看今天有哪些热点适合借势"
python run.py "生成下周小红书的5个内容选题brief"
python run.py "分析麦当劳昨天在抖音发了什么内容"
python run.py "帮我复盘上周五一活动的渠道表现"
```

### 3. 其他常用命令

```bash
python run.py --list        # 查看所有场景 + ROI 汇总
python run.py --history     # 查看最近执行记录
python run.py --recipes     # 查看已归纳的可复用菜谱
python run.py --intake      # 录入新业务痛点
```

---

## 录入新场景（痛点 → 自动化配置）

当你发现了新的营销工作痛点，可以通过交互式工具将其结构化并加入框架：

```bash
python -m framework.pain_point_intake
```

工具会引导你：
1. **描述痛点**：场景名称、痛点描述、当前耗时、期望输出
2. **可行性评分**：5 个维度（执行频率 / 规则清晰度 / 决策链 / 数据可获取性 / 输出标准化），自动生成 0-100% 可行性分数
3. **拆解工作流**：逐步录入执行步骤
4. **生成配置**：LLM 自动生成完整 `scenario_registry.json` 配置条目，可一键加入注册表

---

## 项目结构

```
brand-radar-agent/
├── v1_basic/              # 迭代一：基础单轮 Prompt
│   └── agent.py
├── v2_structured/         # 迭代二：结构化输出 + Pydantic Schema
│   ├── schemas.py
│   └── agent.py
├── v3_agent/              # 迭代三：完整 ReAct Agent + Function Calling
│   ├── tools.py           # 4个工具（搜索/热点/飞书推送/历史存档）
│   └── agent.py
├── framework/             # 通用多场景框架（第四层封装）
│   ├── agent_runner.py    # 场景路由引擎
│   ├── context_manager.py # 双层上下文管理
│   ├── pain_point_intake.py  # 痛点录入工具
│   └── scenario_registry.json  # 场景配置中心
├── scenarios/
│   └── tools_extended.py  # 3个扩展场景的6个专用工具
├── memory/                # 跨会话持久化记忆（自动生成）
├── docs/
│   └── presentation.html  # 交互式项目展示
└── SKILL.md               # 本文件
```

---

## 架构设计亮点

### 三层记忆机制

```
Layer 1 — 执行中压缩（每5次工具调用触发）
  工具调用结果堆积 → LLM 生成「进度快照」→ 替换工具结果
  效果：长任务不撑爆 context window，关键信息零损失

Layer 2 — 任务后持久化（每次任务结束自动保存）
  任务输出 + 关键发现 + 下一步行动 → JSON 写入 memory/{场景}/
  下次运行时自动加载最近 N 条历史 → 跨会话连续性

Layer 3 — 菜谱归纳（Session 执行经验沉淀）
  任务结束后 LLM 自动提炼：解决了什么问题 / 有效工具顺序 / 关键发现 / 注意事项
  写入 memory/recipes/{场景}/，遇到相似任务时自动召回注入 system prompt
  效果：经验不流失，同类任务越跑越快、越跑越准

查看已积累的菜谱：python run.py --recipes
```

### 场景路由逻辑

```
用户输入自然语言
    ↓
关键词快速匹配（scenario_registry.json 中的 trigger_keywords）
    ↓ 未匹配
LLM 语义理解 → 选出最匹配场景ID
    ↓
加载该场景的 system_prompt + tools → 执行 ReAct 循环
```

---

## 迭代演进记录

| 版本 | 核心改进 | 解决问题 |
|------|---------|---------|
| V1 基础版 | 单轮 Prompt，人工输入内容 | POC 验证可行性 |
| V2 结构化 | Pydantic Schema 约束输出，威胁分级 | 输出不稳定、格式混乱 |
| V3 Agent | Function Calling + ReAct + 飞书推送 | 数据全靠人工、无法自动执行 |
| V4 框架化 | 多场景注册表 + 通用路由 + 上下文管理 | 场景固化、无法扩展、长任务超窗 |

---

## 扩展工具对接（生产环境替换）

当前 Demo 使用 Mock 数据，生产环境只需替换以下函数实现，接口不变：

| 工具函数 | Mock 数据 | 生产替换目标 |
|---------|---------|------------|
| `search_social_content` | 静态样本 | 蝉妈妈 API / 新红 API |
| `get_trending_topics` | 固定热榜 | 微博热搜 API / 抖音热榜 |
| `send_feishu_report` | httpx POST | 已对接，填入真实 Webhook |
| `get_brand_calendar` | 模拟日历 | 飞书文档 / 企业日历 API |
| `calculate_campaign_metrics` | 规则计算 | 广告平台 API（巨量引擎等）|

---

## 技术栈

- **LLM**: OpenAI GPT-4o-mini（生产可替换为 Claude / 文心 / 通义）
- **Structured Output**: Pydantic v2 + `response_format`
- **Function Calling**: OpenAI Tool Use，ReAct 推理循环
- **上下文管理**: 自研双层压缩 + JSON 持久化
- **消息推送**: 飞书 Webhook Card 消息
- **CLI**: Rich 终端美化
