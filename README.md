# Marketing Agent OS

一个面向品牌营销团队的多场景 AI Agent 框架，用自然语言描述任务，Agent 自动完成执行、推送结果、积累经验。

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-Function_Calling-green)](https://platform.openai.com)
[![Feishu](https://img.shields.io/badge/Feishu-Webhook-orange)](https://open.feishu.cn)

**[→ 交互式演示](docs/presentation.html)**

---

## 这个项目解决什么问题

品牌营销团队有大量工作是**高频、重复、规则明确**的——竞品监控、选题策划、活动复盘、热点追踪。这类工作的共同特征是：人做和 AI 做的差距不大，但人做要花几小时，AI 做只需几分钟。

这个项目从「竞品社媒监控」这个最典型的痛点切入：

> 原来的做法：每周打开小红书搜竞品 → 截图 → 换平台再搜 → 粘贴整理成 Word → 发给团队。一套下来 3-4 小时，格式每次不一样，发完就过时了。

> 现在的做法：`python run.py "帮我分析麦当劳今天在小红书发了什么"` — 约 2 分钟，结果直接推送飞书，下次遇到类似任务还会自动参考上次的经验。

从这个痛点出发，经过四轮迭代，项目演进为一个支持多场景的通用框架，可以自由扩展到任何具备相同特征的营销工作。

---

## 快速开始

```bash
# 第一步：安装依赖
pip install -r requirements.txt

# 第二步：配置密钥和品牌信息
cp .env.example .env
# 用文本编辑器打开 .env，填入 OPENAI_API_KEY 和 TARGET_BRAND

# 第三步：运行
python run.py "帮我分析麦当劳今天在小红书发了什么内容"
```

支持多种大模型，在 `.env` 中切换 `LLM_PROVIDER` 即可使用 Claude、DeepSeek、月之暗面等。详见 `.env.example`。

---

## 使用方式

用自然语言描述你想做的事，Agent 会自动判断属于哪个场景并执行：

```bash
python run.py "麦当劳最近在小红书的内容风格有什么变化？"
python run.py "帮我生成母亲节小红书内容 brief，3 条"
python run.py "复盘上周五一活动的各渠道表现"
python run.py "今天有没有适合餐饮品牌借势的热点话题"
```

其他命令：

```bash
python run.py --list          # 查看所有支持的场景及预估节省工时
python run.py --history       # 查看过去的执行记录
python run.py --experience    # 查看 Agent 已积累的执行经验
python run.py --intake        # 引导式录入新的业务痛点（5 分钟新增一个场景）
```

---

## 支持的场景

| 场景 | 适用情况 | 每次耗时 | 预计节省 |
|------|---------|---------|---------|
| **竞品分析** | 想了解竞品在某平台的内容策略和近期动作 | ~5 分钟 | ~4h/周 |
| **内容选题 & Brief** | 需要生成近期内容方向和创作指引 | ~3 分钟 | ~3h/周 |
| **Campaign 复盘** | 活动结束后整理各渠道数据和结论 | ~4 分钟 | ~2h/周 |
| **热点预警** | 判断当前热点是否适合品牌借势及如何切入 | ~3 分钟 | ~3h/周 |

描述任务时不需要指定场景名称，Agent 通过关键词匹配和语义理解自动路由。

---

## 核心机制

**Agent 是什么：** 不同于普通的 AI 对话，Agent 会自己决定「先做什么、再做什么」。给它一个目标，它会自主调用工具（搜索内容、查热点、推送报告），直到任务完成。

**三层记忆：** Agent 执行过程中有三个层次的记忆机制，保证长任务不出错、历史经验不丢失。

```
执行中压缩   每 5 次工具调用自动压缩一次，防止超出模型上下文限制
任务后持久化 任务完成后自动存档，下次启动时加载相关历史
执行经验沉淀 每次执行结束提炼成结构化经验，遇到相似任务自动召回参考
```

**扩展新场景：** 遇到新的重复性工作，不需要写代码，运行 `python run.py --intake`，按引导填写痛点描述、执行步骤和预期输出，5 分钟生成配置并加入框架。

---

## 版本演进

这个项目经历了四轮迭代，每轮迭代都针对上一版暴露的具体问题：

**V1 — 验证可行性**（分支 `v1-poc`）

用最简单的单轮 Prompt 验证 AI 做竞品分析是否可行。验证结论：可行，但输出格式每次不同，无法自动化处理，内容采集依然全靠手工。

**V2 — 结构化输出**（分支 `v2-structured`）

引入 Pydantic Schema，强制模型输出固定格式的 JSON，加入品牌上下文和威胁等级评估，支持多竞品批量处理。解决了格式问题，但数据采集仍是人工瓶颈。

**V3 — 完整 Agent**（分支 `v3-agent`）

引入 Function Calling，Agent 自主调用工具完成数据采集、分析、飞书推送、历史存档的完整链路。全程无需人工介入，端到端约 2 分钟。

**V4 — 框架化**（分支 `main`，当前版本）

将单一场景能力扩展为通用多场景框架：场景注册表支持动态添加，自然语言自动路由，三层记忆机制，以及大模型接口抽象层（支持切换 OpenAI / Claude / DeepSeek 等）。

---

## 项目结构

```
brand-radar-agent/
├── run.py                      入口文件，从这里运行所有功能
├── .env.example                配置模板，复制后填入密钥
├── requirements.txt
│
├── v1_basic/                   V1：单轮 Prompt 验证版
├── v2_structured/              V2：Pydantic 结构化输出版
├── v3_agent/                   V3：ReAct Agent + Function Calling
│
├── framework/                  V4：通用多场景框架
│   ├── llm_client.py           大模型接口抽象（支持多平台切换）
│   ├── agent_runner.py         场景路由引擎 + ReAct 主循环
│   ├── context_manager.py      执行中压缩 + 任务后持久化
│   ├── session_summarizer.py   执行经验沉淀与召回
│   ├── pain_point_intake.py    新场景引导式录入工具
│   └── scenario_registry.json  场景配置注册表
│
├── scenarios/
│   └── tools_extended.py       扩展场景的专用工具集
│
├── memory/                     运行后自动生成，无需手动修改
│   ├── {场景名}/               各场景的任务历史
│   └── experience/{场景名}/    各场景积累的执行经验
│
└── docs/presentation.html      交互式演示文档
```

---

## 接入真实数据

当前 Demo 使用模拟数据跑通完整流程。生产环境只需替换 `v3_agent/tools.py` 中对应函数的实现，接口定义不变：

| 工具 | 当前状态 | 生产替换目标 |
|------|---------|------------|
| `search_social_content` | 模拟数据 | 蝉妈妈 / 新红 / 飞瓜 API |
| `get_trending_topics` | 固定热榜 | 微博热搜 / 抖音热榜 API |
| `send_feishu_report` | 已对接 | 填入真实 Webhook 即可 |

---

## 后续计划

- [ ] 接入真实社媒数据 API
- [ ] 支持 RAG：对历史报告做向量检索，支持跨时间段对比分析
- [ ] 多模态：分析竞品图片和视频内容
- [ ] 定时自动运行：每天早上自动推送竞品动态简报

---

有问题或建议欢迎提 Issue，或发邮件至 stevesky233@gmail.com
