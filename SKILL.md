# Brand Radar Agent — 技能说明

## 这是什么

Brand Radar Agent 是一个面向营销团队的多场景 AI Agent 框架。它解决的核心问题是：**营销人员有大量高频、重复、规则明确的工作，花了大量人力，却没有产生更好的结果。**

## 已内置场景

| 场景 | 触发关键词 | 解决的问题 |
|------|-----------|-----------|
| 竞品社媒监控 | 监控、竞品、分析、搜索 | 每周手动搜各平台竞品内容 3-4h → 2min 自动完成 |
| 内容选题策划 | 选题、内容、策划、方案 | 反复对着空白文档想内容方向 → 基于热点+品牌自动生成 |
| Campaign 复盘 | 复盘、campaign、活动、效果 | 手动整合多平台数据写复盘报告 → 结构化自动归纳 |
| 热点预警 | 热点、话题、trending、舆情 | 依赖手动刷榜单发现热点 → 定期自动监测并推送 |

## 使用方式

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API Key（复制 .env.example 并填写）
cp .env.example .env

# 运行任务（自然语言输入，自动识别场景）
python run.py "帮我分析麦当劳今天在小红书发了什么"

# 查看所有可用场景
python run.py --list

# 录入新业务痛点（5分钟生成新场景）
python run.py --intake

# 查看积累的执行经验
python run.py --experience

# 查看 ROI 统计
python run.py --roi
```

## 切换 LLM 提供商

只需修改 `.env`，代码零改动：

```env
# 使用 OpenAI（默认）
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# 切换到 DeepSeek（国内可用，成本低）
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-...

# 切换到 Claude
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
```

## 扩展新场景

**方法一：自动录入**
```bash
python run.py --intake
```
按引导填写 5 分钟，自动生成场景配置并写入注册表。

**方法二：手动添加**
在 `framework/scenario_registry.json` 中添加新场景配置。

**方法三：添加工具**
在 `scenarios/tools_extended.py` 中添加新工具函数，并在场景配置的 `tools` 字段中声明。

## 生产集成

当前版本使用 Mock 数据演示完整流程。生产环境替换路径：

- `v3_agent/tools.py` → 将 `mock_data` 块替换为真实平台 API（小红书、抖音等）
- `scenarios/tools_extended.py` → 每个函数注释中标注了替换点和推荐的第三方服务
- `framework/scenario_registry.json` → 在 `system_prompt` 中注入品牌真实数据

## 技术架构

```
用户输入（自然语言）
    ↓
场景识别（关键词匹配 → LLM fallback）
    ↓
场景配置加载（scenario_registry.json）
    ↓
ReAct 循环（Think → Tool Call → Observe → repeat）
    ↓
上下文压缩（每 N 次工具调用自动压缩）
    ↓
结果推送（飞书 / 邮件）
    ↓
经验归档（memory/experience/ 供下次召回）
```

## 联系

stevesky233@gmail.com
