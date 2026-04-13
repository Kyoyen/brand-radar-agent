# 🔍 Brand Radar Agent
> 营销竞品内容监控 & 洞察 Agent｜从手动整理到全自动推送的三轮迭代实践

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-Function_Calling-green)](https://platform.openai.com)
[![Feishu](https://img.shields.io/badge/Feishu-Webhook-orange)](https://open.feishu.cn)

---

## 背景：痛点来源于真实工作场景

在快消品牌（KFC）的营销工作中，竞品社媒监控是一项**高频、重复、规则清晰**的工作——

> 每周花 3-4 小时：打开小红书搜「麦当劳」→ 截图 → 打开抖音 → 复制粘贴 → 整理成 Word → 发给团队。
> 格式每次不一样，分析深度参差不齐，而且做完就过时了。

这是典型的「Agent 化」场景：**重复 + 规则清晰 + 决策链短 + ROI 明确**。

---

## 项目结构

```
brand-radar-agent/
├── v1_basic/          # V1：人工驱动，验证 Prompt 可行性
│   └── agent.py
├── v2_structured/     # V2：结构化输出，解决格式一致性
│   ├── agent.py
│   └── schemas.py     # Pydantic Schema 定义
├── v3_agent/          # V3：完整 Agent，Function Calling + 飞书推送
│   ├── agent.py       # Agent 主循环（ReAct 模式）
│   └── tools.py       # 工具定义与实现
├── docs/
│   └── architecture.md
├── examples/
│   └── sample_output.json
├── requirements.txt
└── .env.example
```

---

## 三轮迭代：从 POC 到生产

### V1 — 验证可行性（手动 Prompt）

**做了什么：** 用一个通用 Prompt，把手动复制的竞品内容喂给 GPT，输出文字分析。

**发现的问题：**
- 输出格式每次不一样（有时是段落，有时是列表）
- 没有品牌上下文，分析结论不针对我方
- 内容采集依然靠手工，效率瓶颈未解决

**结论：** 痛点真实存在，AI 分析有价值，但需要结构化。

---

### V2 — 结构化输出（JSON Schema）

**做了什么：**
1. 用 Pydantic 定义 `CompetitorBrief` Schema，强制 GPT 输出标准 JSON
2. 加入「我方品牌」参数，分析结论更具针对性
3. 支持多竞品批量处理，结果按威胁等级自动排序

**效果：**
- 输出格式 100% 一致，可直接接入下游
- 分析准确率（人工核验）从约 60% 提升至约 80%
- 批量处理 3 个竞品仅需约 30 秒

**仍存在的问题：**
- 数据采集仍需手动，耗时约 20 分钟/次
- 没有推送机制，团队还要找人转发

---

### V3 — 完整 Agent（Function Calling）

**做了什么：**

引入 4 个 Function Calling 工具，让 LLM 自主决策调用顺序：

| 工具 | 功能 | 对应痛点 |
|------|------|----------|
| `search_social_content` | 自动抓取竞品社媒内容 | 替代手动采集 |
| `get_trending_topics` | 获取平台热门话题 | 补充热点上下文 |
| `send_feishu_report` | 飞书 Webhook 推送 | 替代手动转发 |
| `save_to_history` | 历史存档 | 支持趋势对比 |

**Agent 任务链：**
```
接收任务
  → search_social_content × (竞品数 × 平台数)
  → get_trending_topics × 平台数
  → [LLM综合分析]
  → send_feishu_report
  → save_to_history × 竞品数
```

**效果：**
- 全程人工介入：**0**（仅需核验飞书推送结果）
- 端到端耗时：约 2 分钟（VS 人工 3-4 小时/周）
- 效率提升：**~90%**
- Prompt 迭代 3 轮后，分析准确率 ≥ **85%**

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY

# 3. 运行 V3 Agent（推荐）
python -m v3_agent.agent

# 或分步体验迭代过程：
python v1_basic/agent.py      # 体验 V1 局限
python -m v2_structured.agent # 体验 V2 结构化
```

---

## 关键技术点

- **OpenAI Structured Output**：用 `response_format=PydanticModel` 强制结构化输出
- **Function Calling / Tool Use**：工具定义分离（`tools.py`），Agent 自主决定调用时机
- **ReAct 模式**：Think → Act（调用工具）→ Observe（处理结果）→ 循环
- **Feishu Webhook**：飞书卡片消息格式，支持颜色、标签、多段落
- **异常回退**：工具失败不中断流程，超轮次强制输出

---

## 可扩展方向

- [ ] 接入真实数据 API（蝉妈妈、新红、飞瓜数据）
- [ ] 加入 RAG：将历史报告向量化，支持「这个月麦当劳和上个月比有什么变化？」
- [ ] 多模态：支持竞品图文/视频内容的视觉分析
- [ ] 接入企业 OA：与日报/周报系统打通

---

*作者 Lumon | Yumchina DICC  | 2025*
