#!/usr/bin/env python3
"""
Marketing Agent OS — 统一入口
==================================
用法：
  python run.py "任务描述"            # 自然语言 → 自动识别场景 → 执行
  python run.py                       # 显示所有场景 + ROI 汇总
  python run.py --list                # 同上
  python run.py --history             # 查看最近执行记录
  python run.py --recipes             # 查看已归纳的场景菜谱
  python run.py --intake              # 录入新业务痛点

示例：
  python run.py "分析麦当劳今天在小红书发了什么"
  python run.py "生成母亲节小红书选题brief，3条"
  python run.py "复盘上周五一活动的渠道表现"
  python run.py "今天有没有适合借势的热点"
"""

import sys
import os
from pathlib import Path

# 确保从项目根目录运行
project_root = Path(__file__).parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def check_env():
    """检查必要的环境变量"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print(Panel(
            "[red]缺少 OPENAI_API_KEY[/red]\n\n"
            "请在项目根目录创建 .env 文件并填入：\n\n"
            "  OPENAI_API_KEY=sk-...\n"
            "  TARGET_BRAND=你的品牌名（如：肯德基）\n"
            "  FEISHU_WEBHOOK=https://open.feishu.cn/...（可选）",
            title="⚠️  配置缺失",
            border_style="red",
        ))
        sys.exit(1)


def cmd_run(task: str):
    """执行任务（核心功能）"""
    check_env()
    from framework.agent_runner import AgentRunner

    brand = os.getenv("TARGET_BRAND", "品牌方")
    runner = AgentRunner()

    console.print(f"\n[bold cyan]任务：[/bold cyan]{task}")
    console.print(f"[dim]品牌：{brand}[/dim]\n")

    result = runner.run_auto(task, brand=brand)

    console.print(Panel(
        result,
        title="✅ 执行结果",
        border_style="green",
        padding=(1, 2),
    ))


def cmd_list():
    """显示所有场景"""
    from framework.agent_runner import AgentRunner
    runner = AgentRunner()
    runner.list_scenarios()
    runner.show_roi_summary()

    console.print("\n[dim]使用方式：python run.py \"任务描述\"[/dim]")
    console.print("[dim]示例：  python run.py \"帮我分析麦当劳今天在小红书的动态\"[/dim]\n")


def cmd_history():
    """查看最近执行记录"""
    from framework.context_manager import ContextManager

    memory_dir = project_root / "memory"
    if not memory_dir.exists():
        console.print("[dim]暂无执行记录。运行一次任务后将自动生成。[/dim]")
        return

    table = Table(title="最近执行记录", show_lines=True)
    table.add_column("场景", style="cyan", width=22)
    table.add_column("日期", width=12)
    table.add_column("任务", width=40)
    table.add_column("工具调用", width=8)

    count = 0
    for scenario_dir in sorted(memory_dir.iterdir()):
        if not scenario_dir.is_dir() or scenario_dir.name == "recipes":
            continue
        for session_file in sorted(scenario_dir.glob("*.json"), reverse=True)[:3]:
            try:
                import json
                with open(session_file, encoding="utf-8") as f:
                    data = json.load(f)
                table.add_row(
                    scenario_dir.name,
                    data.get("date", "")[:10],
                    data.get("task_description", "")[:38],
                    str(data.get("metadata", {}).get("tool_calls", "-")),
                )
                count += 1
            except Exception:
                continue

    if count == 0:
        console.print("[dim]暂无执行记录。[/dim]")
    else:
        console.print(table)


def cmd_recipes():
    """查看已归纳的场景菜谱"""
    from framework.session_summarizer import SessionSummarizer
    summarizer = SessionSummarizer()
    recipes = summarizer.list_recipes()

    if not recipes:
        console.print("[dim]暂无菜谱。执行任务后将自动生成，可供后续同类任务复用。[/dim]")
        return

    table = Table(title="场景菜谱库", show_lines=True)
    table.add_column("场景", style="cyan", width=22)
    table.add_column("日期", width=12)
    table.add_column("解决的问题", width=40)
    table.add_column("任务摘要", width=30)

    for r in recipes:
        table.add_row(
            r.get("scenario", ""),
            r.get("date", ""),
            r.get("problem_solved", "")[:38],
            r.get("task", "")[:28],
        )
    console.print(table)
    console.print(f"\n[dim]共 {len(recipes)} 条菜谱。遇到相似任务时，Agent 将自动加载参考。[/dim]\n")


def cmd_intake():
    """录入新业务痛点"""
    check_env()
    import subprocess
    subprocess.run([sys.executable, "-m", "framework.pain_point_intake"])


def show_help():
    console.print(Panel(
        Text.from_markup(
            "[bold]Marketing Agent OS[/bold] — 营销场景自动化工作台\n\n"
            "[cyan]python run.py \"任务描述\"[/cyan]         执行任务（推荐）\n"
            "[cyan]python run.py --list[/cyan]              查看所有场景 + ROI\n"
            "[cyan]python run.py --history[/cyan]           查看最近执行记录\n"
            "[cyan]python run.py --recipes[/cyan]           查看可复用场景菜谱\n"
            "[cyan]python run.py --intake[/cyan]            录入新业务痛点\n\n"
            "[dim]示例任务：[/dim]\n"
            "  • 分析麦当劳今天在小红书发了什么内容\n"
            "  • 生成母亲节小红书选题brief，3条\n"
            "  • 复盘上周五一活动的渠道表现\n"
            "  • 今天有没有适合借势的热点话题"
        ),
        title="📖 使用帮助",
        border_style="cyan",
    ))
    cmd_list()


# ─── 主入口 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        show_help()
    elif args[0] == "--list":
        cmd_list()
    elif args[0] == "--history":
        cmd_history()
    elif args[0] == "--recipes":
        cmd_recipes()
    elif args[0] == "--intake":
        cmd_intake()
    elif args[0].startswith("--"):
        console.print(f"[red]未知参数：{args[0]}[/red]")
        show_help()
    else:
        task = " ".join(args)
        cmd_run(task)
