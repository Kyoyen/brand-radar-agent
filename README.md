# Brand Radar Agent

一个面向品牌营销团队的多场景 AI Agent 框架。用自然语言描述任务，Agent 自动完成执行、推送结果、积累经验。

> **联系**：stevesky233@gmail.com | **演示**：[打开展示页](docs/presentation.html)

---

## 解决什么问题

营销团队有大量工作是**高频、重复、规则明确**的——竞品监控、内容选题、Campaign 复盘、热点预警。这类工作的共同特征是：

- 人做需要 2-4 小时，结果却只用 5 分钟
- 每次格式不一样，依赖个人经验难以传承
- 做完就过时，下次还要重来一遍

**这个项目验证了一个判断**：对于「步骤固定、数据可获取、输出格式明确」的营销工作，AI Agent 可以在保持同等结果质量的前提下，把执行时间压缩到原来的 1/20。

**当前状态**：完整框架 + 部分真实 API + Mock 数据兜底。
- 已接入真实数据源：Google Trends、HackerNews、微博热搜（公开聚合源）、URL 抓取
- 仍为 Mock：小红书、抖音（无官方开放 API，需第三方付费服务，接入路径见 [docs/api_integration.md](docs/api_integration.md)）
- 输出范式：观察 → 洞察 → 决策点 → 建议（带置信度和依据），每条建议可追溯到具体数据点

---

## 四轮迭代路径

```
V1 — 验证可行性（v1-poc 分支）
  单脚本 + 硬编码数据，证明「AI 能完成这类任务」
  关键结论：ReAct 模式适用于营销监控场景

V2 — 结构化输出（v2-structured 分支）
  引入 Pydantic Schema，输出从自由文本变为结构化 JSON
  关键结论：结构化输出是 Agent 结果可信赖的前提

V3 — 工具调用（v3-agent 分支）
  OpenAI Function Calling，Agent 自主决策调用哪些工具
  关键结论：工具调用显著提升了任务完成的灵活性

V4 — 通用框架（main 分支，当前）
  多场景路由 + LLM 接口抽象 + 三层记忆 + 5分钟录入新场景
  关键结论：框架化后，扩展新场景从「重新开发」变为「填写配置」
```

---

## 核心能力

**多场景路由**：一个入口，自动识别任务类型，分发到对应场景

**LLM 无锁定**：`.env` 一行切换 OpenAI / Claude / DeepSeek / 月之暗面，业务代码零改动

**三层记忆**：
- 执行中压缩（防止超出上下文限制）
- 任务后持久化（跨会话历史记忆）
- 经验归档（相似任务自动召回上次的教训和结论）

**5分钟录入新场景**：`python run.py --intake` 引导式问答，自动生成场景配置

---

## 已内置场景

| 场景 | 解决的问题 | 当前耗时节省 |
|------|-----------|------------|
| 竞品社媒监控 | 手动搜各平台截图整理 → 自动执行并推送飞书 | ~3h → ~2min |
| 内容选题策划 | 对着空文档想方向 → 基于热点+品牌定位自动生成 | ~1h → ~3min |
| Campaign 复盘 | 手动整合多平台数据写报告 → 结构化自动归纳 | ~2h → ~5min |
| 热点预警 | 手动刷榜单发现机会 → 定期自动监测并推送 | 持续人工 → 零值守 |

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置（复制并填写 API Key）
cp .env.example .env

# 运行任务（自动识别场景）
python run.py "帮我分析麦当劳今天在小红书发了什么"

# 查看所有场景
python run.py --list

# 查看 ROI 汇总
python run.py --roi

# 录入新业务痛点（5分钟）
python run.py --intake

# 查看积累的执行经验
python run.py --experience
```

---

## 切换 LLM

```env
# .env 文件，只改这两行，代码不动

# 国内首选（成本低，速度快）
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-...

# 默认
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Anthropic Claude
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 项目结构

```
brand-radar-agent/
├── run.py                      # 统一入口（所有操作从这里开始）
├── framework/
│   ├── agent_runner.py         # 多场景路由 + ReAct 主循环
│   ├── llm_client.py           # LLM 接口抽象（多平台统一接口）
│   ├── context_manager.py      # 双层上下文管理（压缩 + 持久化）
│   ├── session_summarizer.py   # 执行经验归档与召回
│   ├── pain_point_intake.py    # 5分钟录入新场景
│   └── scenario_registry.json  # 场景配置注册表
├── v3_agent/
│   ├── agent.py                # ReAct Agent 核心（可独立运行）
│   └── tools.py                # 工具集（Mock，标注生产替换点）
├── scenarios/
│   └── tools_extended.py       # 扩展工具（Campaign复盘、情感分析等）
├── memory/                     # 运行时自动生成（历史记忆 + 经验库）
├── docs/
│   └── presentation.html       # 交互式演示页
└── v1_basic/ v2_structured/    # 历史版本归档（对应各分支）
```

---

## 输出范式

所有场景统一输出四段式结构（`framework/output_schema.py`），辅助决策而不是甩数据：

```
观察 (O1, O2, ...)     客观事实，必须有数据来源
  ↓
洞察 (I1, I2, ...)     基于观察的判断，evidence_refs 指向 O
  ↓
决策点 (D1, D2, ...)   用户面临的选择，给出选项
  ↓
推荐行动 (A1, A2, ...) 具体行动，带 priority / effort / confidence
```

每条洞察、决策、建议都通过 `evidence_refs` 追溯到具体观察。Agent 输出 JSON 后自动解析为 Markdown，可直接推送飞书/邮件。

## 生产集成路径

详见 [docs/api_integration.md](docs/api_integration.md)，覆盖：

- 已开箱即用：Google Trends / HackerNews / 微博热搜 / URL 抓取
- 国内社媒：小红书（新红/千瓜）、抖音（飞瓜/蝉妈妈）、微博官方
- 推送通道：飞书 webhook、SMTP 邮件
- LLM 平台：5 家对比与切换

框架层（路由、记忆、LLM 抽象、输出范式）无需修改，新增工具只需在 `scenarios/tools_real.py` 加一个函数。

---

## 技术路径反思

**真正可落地的场景（高信心）**：执行步骤固定、输出格式明确、数据可程序化获取的重复性工作。

**需要谨慎的场景**：涉及创意判断、多人协作决策、或数据获取依赖人工登录的工作。AI 目前替代的是「信息整理」，而非「策略判断」。

这个项目的核心价值在于验证了一套「营销工作 Agent 化」的工程模式：哪些步骤可以 Agent 化、哪些需要人工兜底、如何让系统越用越聪明。

---

*MIT License*
