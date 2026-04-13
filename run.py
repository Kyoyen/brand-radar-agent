#!/usr/bin/env python3
"""
Marketing Agent OS — 统一入口
==================================
用法：
  python run.py "任务描述"            # 自然语言 → 自动识别场景 → 执行
  python run.py                       # 显示所有场景 + ROI 汇总
  python run.py --list                # 查看所有可用场景
  python run.py --history             # 查看最近执行记录
  python run.py --experience          # 查看已积累的执行经验
  python run.py --intake              # 引导式录入新业务痛点

示例：
  python run.py "分析麦当劳今天在小红书发了什么"
  python run.py "生成母亲节小红书选题brief，3条"
  python run.py "复盘上周五一活动的渠道表现"
  python run.py "今天有没有适合借势的热点"
"""

import sys
import os
import json
from pathlib import Path

# 确保从项目根目录运行，所有相对路径基于此
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


# ─── 环境检查 ──────────────────────────────────────────────────────────────────

def check_env():
    """检查必要的环境变量，缺失时给出明确提示"""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    key_map = {
        "openai":    "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek":  "DEEPSEEK_API_KEY",
        "moonshot":  "MOONSHOT_API_KEY",
        "zhipu":     "ZHIPU_API_KEY",
    }
    required_key = key_map.get(provider, "OPENAI_API_KEY")

    if not os.getenv(required_key):
        console.print(Panel(
            f"[red]缺少 {required_key}[/red]\n\n"
            f"请在项目根目录创建 .env 文件：\n\n"
            f"  cp .env.example .env\n\n"
            f"然后打开 .env，填入你的 API 密钥。\n"
            f"参考 .env.example 中的说明，支持 OpenAI / Claude / DeepSeek 等。",
            title="⚠️  配置缺失",
            border_style="red",
        ))
        sys.exit(1)


# ─── 核心命令 ──────────────────────────────────────────────────────────────────

def cmd_run(task: str):
    """执行任务（核心功能）：自然语言 → 自动识别场景 → 执行 → 推送飞书 → 沉淀经验"""
    check_env()
    from framework.agent_runner import AgentRunner

    brand = os.getenv("TARGET_BRAND", "品牌方")
    runner = AgentRunner()

    console.print(Panel(
        f"[bold]{task}[/bold]\n[dim]品牌：{brand}[/dim]",
        title="🚀 开始执行",
        border_style="cyan",
    ))

    result = runner.run_auto(task, brand=brand)

    console.print(Panel(
        result,
        title="✅ 执行完成",
        border_style="green",
        padding=(1, 2),
    ))


def cmd_list():
    """显示所有可用场景及 ROI 汇总"""
    from framework.agent_runner import AgentRunner
    runner = AgentRunner()
    runner.list_scenarios()
    runner.show_roi_summary()
    console.print()
    console.print("[dim]运行任务：python run.py \"任务描述\"[/dim]")
    console.print("[dim]示例：    python run.py \"帮我分析麦当劳今天在小红书的动态\"[/dim]\n")


def cmd_history():
    """查看最近执行记录"""
    memory_dir = project_root / "memory"
    if not memory_dir.exists():
        console.print("[dim]暂无记录。运行一次任务后自动生成。[/dim]")
        return

    table = Table(title="最近执行记录", show_lines=True)
    table.add_column("场景", style="cyan", width=22)
    table.add_column("日期", width=12)
    table.add_column("任务", width=42)
    table.add_column("工具调用次数", width=10)

    count = 0
    for scenario_dir in sorted(memory_dir.iterdir()):
        # 跳过经验库子目录
        if not scenario_dir.is_dir() or scenario_dir.name == "experience":
            continue
        for session_file in sorted(scenario_dir.glob("*.json"), reverse=True)[:3]:
            try:
                with open(session_file, encoding="utf-8") as f:
                    data = json.load(f)
                table.add_row(
                    scenario_dir.name,
                    data.get("date", "")[:10],
                    data.get("task_description", "")[:40],
                    str(data.get("total_tool_calls", "-")),
                )
                count += 1
            except Exception:
                continue

    if count == 0:
        console.print("[dim]暂无执行记录。[/dim]")
    else:
        console.print(table)
        console.print(f"\n[dim]共 {count} 条记录 | 完整文件见 memory/ 目录[/dim]\n")


def cmd_experience():
    """查看已积累的执行经验（Agent 自动从这里学习如何更好地执行同类任务）"""
    from framework.session_summarizer import SessionSummarizer
    summarizer = SessionSummarizer()
    records = summarizer.list_experience()

    if not records:
        console.print(Panel(
            "暂无执行经验记录。\n\n"
            "每次运行任务后，Agent 会自动提炼本次执行过程并存入经验库。\n"
            "下次遇到相似任务时，会自动从经验库中召回参考。",
            title="📚 执行经验库",
            border_style="dim",
        ))
        return

    table = Table(title=f"执行经验库（共 {len(records)} 条）", show_lines=True)
    table.add_column("场景", style="cyan", width=22)
    table.add_column("日期", width=12)
    table.add_column("解决的问题", width=45)

    for r in records:
        table.add_row(
            r.get("scenario", ""),
            r.get("date", ""),
            r.get("problem_solved", "")[:43],
        )
    console.print(table)
    console.print(f"\n[dim]Agent 在执行相似任务时会自动加载这些经验作为参考。[/dim]\n")


def cmd_intake():
    """引导式录入新业务痛点，自动生成场景配置"""
    check_env()
    import subprocess
    subprocess.run([sys.executable, "-m", "framework.pain_point_intake"])


# ─── 帮助页 ────────────────────────────────────────────────────────────────────

def show_help():
    console.print(Panel(
        Text.from_markup(
            "[bold]Marketing Agent OS[/bold] — 营销场景自动化工作台\n\n"
            "[bold cyan]python run.py \"任务描述\"[/bold cyan]      执行任务（核心功能）\n"
            "[cyan]python run.py --list[/cyan]             查看所有场景 + ROI\n"
            "[cyan]python run.py --history[/cyan]          查看最近执行记录\n"
            "[cyan]python run.py --experience[/cyan]       查看已积累的执行经验\n"
            "[cyan]python run.py --intake[/cyan]           录入新业务痛点\n\n"
            "[dim]── 任务示例 ──────────────────────────────────────[/dim]\n"
            "  python run.py \"分析麦当劳今天在小红书发了什么内容\"\n"
            "  python run.py \"生成母亲节小红书选题brief，3条\"\n"
            "  python run.py \"复盘上周五一聚餐季活动的渠道表现\"\n"
            "  python run.py \"今天有没有适合餐饮品牌借势的热点\"",
        ),
        title="📖 使用帮助",
        border_style="cyan",
    ))
    console.print()
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
    elif args[0] in ("--experience", "--exp"):
        cmd_experience()
    elif args[0] == "--intake":
        cmd_intake()
    elif args[0].startswith("--"):
        console.print(f"[red]未知参数：{args[0]}[/red]\n")
        show_help()
    else:
        task = " ".join(args)
        cmd_run(task)
