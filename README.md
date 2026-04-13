# Marketing Agent OS — 营销场景自动化工作台

> 从竞品分析出发，演进为可扩展的多场景营销 Agent 框架。
> 自然语言驱动，结果自动推送飞书，执行经验自动沉淀为可复用菜谱。

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-Function_Calling-green)](https://platform.openai.com)
[![Feishu](https://img.shields.io/badge/Feishu-Webhook-orange)](https://open.feishu.cn)

**[→ 交互式演示文档](docs/presentation.html)**

---

## 背景：从一个真实痛点开始

在快消品牌（KFC）营销工作中，竞品社媒监控是一项**高频、重复、规则清晰**的工作——

> 每周花 3-4 小时：打开小红书搜「麦当劳」→ 截图 → 打开抖音 → 复制粘贴 → 整理成 Word → 发给团队。
> 格式每次不一样，分析深度参差不齐，而且做完就过时了。

这是典型的 Agent 化场景：**重复 + 规则清晰 + 决策链短 + ROI 明确**。
从这个痛点出发，经过四轮迭代，最终形成支持 4 个营销场景的通用框架。

---

## 快速开始（3 步）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 和 TARGET_BRAND

# 3. 用自然语言描述任务
python run.py "帮我分析麦当劳今天在小红书发了什么内容"
```

---

## 常用命令

```bash
python run.py "任务描述"        # 执行任务（核心功能）
python run.py --list            # 查看所有可用场景 + ROI 汇总
python run.py --history         # 查看最近执行记录
python run.py --recipes         # 查看可复用的场景菜谱
python run.py --intake          # 引导式录入新业务痛点
```

任务示例：

```bash
python run.py "麦当劳最近在小红书的内容风格有什么变化？"
python run.py "帮我生成母亲节小红书内容brief，3条"
python run.py "帮我复盘上周五一聚餐季活动的渠道表现"
python run.py "今天有没有适合餐饮品牌借势的热点"
```

---

## 支持场景

| 场景 | 触发词示例 | 耗时 | 周节省工时 |
|------|-----------|------|---------|
| **竞品分析** | 竞品、分析、麦当劳、汉堡王 | ~5min | ~4h |
| **内容选题 & Brief** | 选题、brief、内容方向、排期 | ~3min | ~3h |
| **Campaign 复盘** | 复盘、数据、渠道表现、总结 | ~4min | ~2h |
| **热点预警** | 热点、借势、话题、趋势 | ~3min | ~3h |

Agent 通过**关键词匹配 + LLM 语义兜底**自动识别场景，无需手动指定。

---

## 四轮迭代记录

### V1 — 验证可行性（`v1_basic/`）

**做了什么：** 单轮 Prompt，手动输入竞品内容，GPT 输出文字分析。

**发现的问题：** 输出格式每次不一样；没有品牌上下文；内容采集仍靠手工。

**结论：** 痛点真实，AI 分析有价值，但需要结构化约束。

---

### V2 — 结构化输出（`v2_structured/`）

**做了什么：** 用 Pydantic 定义 `CompetitorBrief` Schema，强制输出标准 JSON；加入品牌上下文；支持多竞品批量处理并按威胁等级排序。

```python
# 关键改动：response_format 约束输出
response = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    response_format=CompetitorBrief,
    temperature=0.3,
)
```

**效果：** 输出格式 100% 一致；人工核验准确率从约 60% 提升至约 80%；批量处理 3 个竞品约 30 秒。

**仍存在的问题：** 数据采集仍需手动（约 20 分钟/次）；没有推送机制。

---

### V3 — ReAct Agent（`v3_agent/`）

**做了什么：** 引入 4 个 Function Calling 工具，Agent 自主决策调用顺序：

| 工具 | 功能 | 替代的人工操作 |
|------|------|-------------|
| `search_social_content` | 自动抓取竞品社媒内容 | 手动刷平台 |
| `get_trending_topics` | 获取平台热门话题 | 手动查热榜 |
| `send_feishu_report` | 飞书 Webhook 推送 | 手动转发整理 |
| `save_to_history` | 历史存档 | 手动建档 |

```python
# 关键改动：Agent 自主调用工具，ReAct 循环
while turn < MAX_TURNS:
    response = client.chat.completions.create(tools=TOOLS, tool_choice="auto")
    if finish_reason == "stop": break
    for tool_call in msg.tool_calls:
        result = execute_tool(tool_call.function.name, args)
```

**效果：** 全程人工介入 0 次；端到端 ~2 分钟（vs 人工 3-4 小时/周）；效率提升约 90%。

---

### V4 — 框架化（`framework/` + `run.py`）

**做了什么：** 将单场景能力扩展为可复用的多场景工作台，解决三个问题：

1. **场景固化** → `scenario_registry.json` 注册表 + `pain_point_intake.py` 5 分钟添加新场景
2. **长任务超窗** → `context_manager.py` 双层压缩（执行中 + 持久化）
3. **经验无法积累** → `session_summarizer.py` 自动归纳菜谱，下次同类任务召回复用

**核心新增：**

```
framework/
├── agent_runner.py        路由引擎（关键词 + LLM 自动路由）
├── context_manager.py     双层上下文管理
├── session_summarizer.py  Session 归纳 → 可复用菜谱（新增）
├── pain_point_intake.py   痛点录入工具
└── scenario_registry.json 场景配置注册表（4 个内置场景）
```

**效果：** 4 个场景，周节省约 12h 工时；新场景录入从「写代码（数小时）」降为「引导式录入（5分钟）」；每次执行自动沉淀为可复用菜谱。

---

## 三层记忆机制

```
执行中压缩（Layer 1）
  每 5 次工具调用触发 → LLM 生成进度快照 → 替换工具结果
  作用：防止长任务超出 context window

任务后持久化（Layer 2）
  任务结束写入 memory/{场景}/ → 下次任务自动加载
  作用：跨会话连续性，记住上次做了什么

菜谱归纳（Layer 3 · 新增）
  任务结束 LLM 提炼执行过程 → 写入 memory/recipes/
  内容：解决了什么问题 / 有效工具顺序 / 关键发现 / 注意事项
  作用：遇到相似任务时自动召回，加速执行并避免重复踩坑
```

---

## 扩展新场景

```bash
python run.py --intake
```

引导式录入流程：

1. 描述痛点（场景名称、当前耗时、期望输出）
2. 5 维可行性评分（执行频率 / 规则清晰度 / 决策链 / 数据可获取性 / 输出标准化）
3. 拆解执行步骤
4. LLM 自动生成场景配置 → 加入 `scenario_registry.json`

---

## 文件结构

```
brand-radar-agent/
├── run.py                     ← 统一入口（从这里开始）
├── .env.example               ← 环境变量模板
├── requirements.txt
│
├── v1_basic/                  ← 迭代一：单轮 Prompt
├── v2_structured/             ← 迭代二：Pydantic 结构化输出
├── v3_agent/                  ← 迭代三：ReAct + Function Calling
│
├── framework/                 ← 迭代四：通用多场景框架
│   ├── agent_runner.py
│   ├── context_manager.py
│   ├── session_summarizer.py  ← Session 归纳 & 菜谱复用
│   ├── pain_point_intake.py
│   └── scenario_registry.json
│
├── scenarios/
│   └── tools_extended.py      ← 扩展场景专用工具
│
├── memory/                    ← 自动生成，勿手动修改
│   ├── {场景}/                任务持久化记忆
│   └── recipes/{场景}/        可复用场景菜谱
│
└── docs/presentation.html     ← 交互式演示文档
```

---

## 可扩展方向

- [ ] 接入真实数据 API（蝉妈妈、新红、飞瓜数据）
- [ ] 加入 RAG：将历史报告向量化，支持「这个月麦当劳和上个月比有什么变化？」
- [ ] 多模态：支持竞品图文/视频内容的视觉分析
- [ ] 接入企业 OA：与日报/周报系统打通

---

<<<<<<< Updated upstream
*作者 Lumon | Yumchina DICC  | 2025*
=======
## 环境变量

```bash
OPENAI_API_KEY=sk-...                        # 必填
TARGET_BRAND=肯德基                           # 你的品牌名
FEISHU_WEBHOOK=https://open.feishu.cn/...    # 可选，飞书报告推送
```

---

*作者：石珂源 | 百胜中国 DICC · 市场专员 | 2025*
>>>>>>> Stashed changes
