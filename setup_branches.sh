#!/bin/bash
# =============================================================
# Marketing Agent OS — 一键建立 git 分支体系
# 运行方式：
#   cd ~/Desktop/resume/brand-radar-agent
#   bash setup_branches.sh
#
# 执行后 GitHub 上会出现 4 个分支：
#   main          完整框架（V4，最新，永远保持最新）
#   v3-agent      ReAct Agent + Function Calling（不含 framework/）
#   v2-structured 结构化输出版本（不含 v3/framework/）
#   v1-poc        最初 POC 版本（仅 v1_basic/）
# =============================================================

set -e   # 任何命令失败立刻停止

cd "$(dirname "$0")"
echo "📁 当前目录：$(pwd)"

# ── Step 0：清理残留锁文件 ─────────────────────────────────────
echo ""
echo "🧹 清理 git 锁文件..."
rm -f .git/index.lock .git/HEAD.lock .git/MERGE_HEAD .git/CHERRY_PICK_HEAD 2>/dev/null || true

# ── Step 1：提交所有当前改动到 main ───────────────────────────
echo ""
echo "📦 提交当前所有改动到 main..."
git add .
git diff --cached --quiet && echo "  (无新改动，跳过 commit)" || \
  git commit -m "feat: V4 完整框架 — LLM接口抽象 + 执行经验沉淀 + 简化入口

- framework/llm_client.py     大模型接口抽象层（支持 OpenAI/Claude/DeepSeek 等）
- framework/session_summarizer.py  执行经验沉淀 & 召回（重构命名）
- framework/context_manager.py    接入 LLMClient，去掉硬编码
- framework/__init__.py           完整导出所有公开类
- run.py                          统一入口，修复 --experience 命令
- .env.example                    完整配置模板，支持多模型切换"

git push origin main
echo "  ✅ main 已推送"

# ── Step 2：创建 v3-agent 分支（只含 v1/v2/v3，不含 framework）─
echo ""
echo "🌿 创建 v3-agent 分支..."
git checkout -b v3-agent
git rm -rf framework/ scenarios/ SKILL.md run.py --quiet 2>/dev/null || true
git add -A
git commit -m "snapshot: V3 ReAct Agent — Function Calling + 飞书推送

此分支为 V3 阶段快照，展示完整 ReAct Agent 实现：
- v3_agent/tools.py  4个工具（社媒搜索/热点/飞书推送/历史存档）
- v3_agent/agent.py  ReAct 主循环，自主决策工具调用顺序

运行：python -m v3_agent.agent" --allow-empty
git push origin v3-agent
git checkout main
echo "  ✅ v3-agent 已推送"

# ── Step 3：创建 v2-structured 分支（只含 v1/v2）──────────────
echo ""
echo "🌿 创建 v2-structured 分支..."
git checkout -b v2-structured
git rm -rf v3_agent/ framework/ scenarios/ SKILL.md run.py --quiet 2>/dev/null || true
git add -A
git commit -m "snapshot: V2 结构化输出 — Pydantic Schema + 威胁分级

此分支为 V2 阶段快照：
- v2_structured/schemas.py  CompetitorBrief Pydantic 模型
- v2_structured/agent.py    结构化输出调用，response_format 约束

运行：python -m v2_structured.agent" --allow-empty
git push origin v2-structured
git checkout main
echo "  ✅ v2-structured 已推送"

# ── Step 4：创建 v1-poc 分支（只含 v1）────────────────────────
echo ""
echo "🌿 创建 v1-poc 分支..."
git checkout -b v1-poc
git rm -rf v2_structured/ v3_agent/ framework/ scenarios/ SKILL.md run.py --quiet 2>/dev/null || true
git add -A
git commit -m "snapshot: V1 POC — 最初可行性验证版本

此分支为 V1 阶段快照：
- v1_basic/agent.py  单轮 Prompt，人工输入内容，验证 AI 分析可行性

运行：python v1_basic/agent.py" --allow-empty
git push origin v1-poc
git checkout main
echo "  ✅ v1-poc 已推送"

# ── 完成 ───────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "✅ 全部完成！GitHub 上现在有 4 个分支："
echo ""
echo "  main           完整 V4 框架（最新，持续更新这个）"
echo "  v3-agent       V3 快照：ReAct Agent + Function Calling"
echo "  v2-structured  V2 快照：Pydantic 结构化输出"
echo "  v1-poc         V1 快照：最初 POC 验证"
echo ""
echo "👉 日常只需要在 main 分支上工作："
echo "   git add . && git commit -m '改了什么' && git push origin main"
echo "=============================================="
