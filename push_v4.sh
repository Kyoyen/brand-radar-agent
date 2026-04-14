#!/bin/bash
# Brand Radar Agent — 一键推送 V4 + 整理所有分支
# 用法：cd ~/Desktop/resume/brand-radar-agent && bash push_v4.sh
#
# 做了什么：
#   1. 清理 git 锁文件
#   2. 在 main 上提交所有新增文件并强制推送
#   3. 给 v1-poc / v2-structured / v3-agent 各自添加分支说明 README 并推送

set -e
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

echo ""
echo "🔧 Brand Radar Agent — 推送 V4 + 整理分支"
echo "─────────────────────────────────────────"

# ── 1. 清理锁文件 ───────────────────────────────────
echo ""
echo "1/4  清理所有 git 锁文件..."
find .git -name "*.lock" -print -delete 2>/dev/null && echo "     done" || echo "     (无锁文件)"

# ── 2. 提交 main 上的所有新文件并推送 ──────────────
echo ""
echo "2/4  提交 main 分支所有变更..."
git checkout main
git add -A

if git diff --cached --quiet; then
  echo "     (无新变更，跳过 commit)"
else
  git commit -m "feat: V4.2 — 结构化输出 + 真实API + 反幻觉约束 + Mock兜底 + ReAct去重

  新能力：
  - 结构化输出范式（framework/output_schema.py）：观察→洞察→决策点→建议
  - 真实 API 工具集（scenarios/tools_real.py）：Google Trends/HackerNews/微博/URL
  - 反幻觉全局约束（agent_runner UNIVERSAL_METHODOLOGY）
  - MockProvider 兜底（llm_client）：无 API Key 也能跑通完整流程
  - ReAct 工具去重：同参数调用 >2 次自动中断，避免死循环
  - 默认 LLM 切换为 DeepSeek（国内首选 + 成本低）

  文档：
  - docs/api_integration.md：小红书/抖音/微博/飞书/SMTP/LLM 接入完整指南"
fi

echo ""
echo "3/4  强制推送 main 到 origin..."
git push --force origin main
echo "     ✅ main 推送完成"

# ── 3. 给各历史分支添加分支说明 README ─────────────

add_branch_readme() {
  local BRANCH=$1
  local CONTENT=$2

  echo ""
  echo "     处理分支: $BRANCH"
  git checkout "$BRANCH" 2>/dev/null || { echo "     (分支不存在，跳过)"; return; }

  # 只写 README，不动其他文件
  echo "$CONTENT" > README.md
  git add README.md

  if git diff --cached --quiet; then
    echo "     (README 无变化，跳过)"
  else
    git commit -m "docs: 添加分支说明 README"
    echo "     ✅ committed"
  fi

  git push origin "$BRANCH" --force
  echo "     ✅ pushed"
}

echo ""
echo "4/4  更新各历史分支 README..."

add_branch_readme "v1-poc" "# Brand Radar Agent — V1 POC

> 这是 V1 版本快照分支，展示最初的可行性验证阶段。

## 这个分支做了什么

用最简单的方式验证一个核心假设：**AI 能做竞品社媒监控这件事吗？**

- 单文件脚本（\`v1_basic/agent.py\`），约 100 行
- 硬编码测试数据，无工具调用，直接提问 LLM
- 输出：纯文本分析报告，格式不固定

## 关键结论

ReAct 模式（Think → Act → Observe）适用于营销监控类任务，但自由文本输出难以程序化处理。
这是推动 V2 引入 Pydantic 结构化输出的直接原因。

## 局限性（故意保留）

- 无工具调用，无法真正调用外部数据
- 输出不可预期，每次结果格式不同
- 无记忆，每次从零开始

**→ 进化到 V2（v2-structured 分支）：引入 Pydantic Schema，结果变为结构化 JSON**

---
联系：stevesky233@gmail.com | [查看 V4 完整框架](https://github.com/kyoyen/brand-radar-agent)"

add_branch_readme "v2-structured" "# Brand Radar Agent — V2 结构化输出

> 这是 V2 版本快照分支，展示引入 Pydantic 结构化输出后的版本。

## 这个分支做了什么

解决 V1 遗留问题：**输出不稳定，结果难以程序化处理**。

- 引入 Pydantic v2 Schema 约束 LLM 输出格式
- 竞品报告输出为结构化 JSON，含威胁等级分级（high/medium/low）
- 可直接接入下游系统（飞书、数据库、看板）

\`\`\`python
class CompetitorReport(BaseModel):
    brand: str
    platform: str
    post_count: int
    threat_level: Literal['high', 'medium', 'low']
    key_findings: list[str]
    recommended_actions: list[str]
\`\`\`

## 关键结论

结构化输出是 Agent 结果「可信赖」的前提。LLM 能力再强，如果输出格式不可控，下游系统就无法消费。

## 局限性（故意保留）

- 执行路径仍然固定，Agent 无法自主决策工具调用顺序
- 数据仍为 Mock，无真实平台 API

**→ 进化到 V3（v3-agent 分支）：OpenAI Function Calling + 真正的工具调用**

---
联系：stevesky233@gmail.com | [查看 V4 完整框架](https://github.com/kyoyen/brand-radar-agent)"

add_branch_readme "v3-agent" "# Brand Radar Agent — V3 ReAct Agent

> 这是 V3 版本快照分支，展示引入工具调用和飞书推送后的版本。

## 这个分支做了什么

解决 V2 遗留问题：**Agent 只能直线执行，无法自主决策工具调用顺序**。

- 接入 OpenAI Function Calling，Agent 自主选择工具和调用顺序
- 实现完整 ReAct 循环（Think → Tool Call → Observe → repeat）
- 结果以飞书卡片格式推送，颜色按威胁等级变化
- 4 个工具：搜索社媒内容、获取热点话题、发送飞书报告、保存历史

## 关键结论

工具调用显著提升了任务灵活性。Agent 可以根据观察结果动态决定下一步：比如发现某个热点后，主动再搜一次相关内容。

## 局限性（故意保留）

- 场景单一（只有竞品监控），扩展需要改代码
- 无跨任务记忆，每次从零开始
- LLM 平台锁定（只支持 OpenAI）

**→ 进化到 V4（main 分支）：多场景路由 + LLM 抽象 + 三层记忆**

---
联系：stevesky233@gmail.com | [查看 V4 完整框架](https://github.com/kyoyen/brand-radar-agent)"

# ── 回到 main ─────────────────────────────────────────
echo ""
git checkout main
echo ""
echo "─────────────────────────────────────────"
echo "✅ 全部完成！"
echo ""
echo "   GitHub：https://github.com/kyoyen/brand-radar-agent"
echo "   分支：main / v1-poc / v2-structured / v3-agent"
echo ""
