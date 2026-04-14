"""
Brand Radar Agent — 统一入口
==============================
用法：
  python run.py "帮我分析麦当劳今天在小红书发了什么"
  python run.py --list
  python run.py --history
  python run.py --experience
  python run.py --intake
  python run.py --roi
"""

import sys
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


# ── 环境检查 ────────────────────────────────────────────────────────────────

def check_env():
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    key_map = {
        "openai":    "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek":  "DEEPSEEK_API_KEY",
        "moonshot":  "MOONSHOT_API_KEY",
        "zhipu":     "ZHIPU_API_KEY",
    }
    env_var = key_map.get(provider, "OPENAI_API_KEY")
    if not os.getenv(env_var):
        print(f"\n❌ 缺少 API Key：{env_var}")
        print(f"   当前 LLM_PROVIDER = {provider}")
        print(f"   请在 .env 文件中设置 {env_var}=your_api_key\n")
        return False
    print(f"  [配置] Provider: {provider} | Key: {env_var[:6]}***")
    return True


# ── 子命令处理 ──────────────────────────────────────────────────────────────

def cmd_run(task: str, brand: str = None):
    from framework import AgentRunner
    runner = AgentRunner()
    kwargs = {}
    if brand:
        kwargs["brand"] = brand
    result = runner.run_auto(task, **kwargs)
    print(f"\n{'='*55}")
    print("最终输出：")
    print(result)


def cmd_list():
    from framework import AgentRunner
    AgentRunner().list_scenarios()


def cmd_roi():
    from framework import AgentRunner
    AgentRunner().show_roi_summary()


def cmd_history():
    from framework.context_manager import ContextManager
    from rich.table import Table
    from rich.console import Console
    import json

    console = Console()
    memory_dir = ROOT / "memory"
    if not memory_dir.exists():
        print("暂无历史记录。")
        return

    t = Table(title="历史执行记录", show_lines=True)
    t.add_column("场景", style="cyan", width=22)
    t.add_column("日期", width=12)
    t.add_column("任务", width=35)
    t.add_column("工具调用", width=8)

    for fp in sorted(memory_dir.glob("**/*.json"), reverse=True)[:20]:
        if "experience" in str(fp):
            continue
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
            t.add_row(
                d.get("scenario", ""),
                d.get("date", ""),
                (d.get("task_description", ""))[:33] + "...",
                str(d.get("total_tool_calls", 0)),
            )
        except Exception:
            continue
    console.print(t)


def cmd_experience(scenario: str = None):
    from framework.session_summarizer import SessionSummarizer
    from rich.table import Table
    from rich.console import Console

    console = Console()
    summarizer = SessionSummarizer()
    records = summarizer.list_experience(scenario)

    if not records:
        print("暂无执行经验。运行任务后会自动积累。")
        return

    t = Table(title="执行经验库", show_lines=True)
    t.add_column("场景", style="cyan", width=22)
    t.add_column("日期", width=12)
    t.add_column("任务", width=30)
    t.add_column("解决了什么", width=35)
    for r in records[:15]:
        t.add_row(r["scenario"], r["date"], r["task"][:28], r["problem_solved"][:33])
    console.print(t)


def cmd_intake():
    from framework.pain_point_intake import PainPointIntake
    PainPointIntake().run_interactive()


# ── 主入口 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Brand Radar Agent — 营销 AI Agent 框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python run.py "分析麦当劳在小红书的最新动态"
  python run.py "生成关于夏日饮品的内容选题" --brand 某品牌
  python run.py --list
  python run.py --history
  python run.py --experience
  python run.py --intake
        """,
    )
    parser.add_argument("task", nargs="?", default=None, help="用自然语言描述任务")
    parser.add_argument("--brand", default=None, help="指定品牌名称（可选）")
    parser.add_argument("--list",       action="store_true", help="列出所有可用场景")
    parser.add_argument("--roi",        action="store_true", help="显示 ROI 汇总")
    parser.add_argument("--history",    action="store_true", help="查看历史执行记录")
    parser.add_argument("--experience", action="store_true", help="查看积累的执行经验")
    parser.add_argument("--intake",     action="store_true", help="录入新业务痛点场景")
    parser.add_argument("--scenario",   default=None,        help="指定场景ID（配合--experience）")

    args = parser.parse_args()

    print("\n🔍 Brand Radar Agent OS")
    print("─" * 40)

    if not check_env():
        sys.exit(1)

    if args.list:
        cmd_list()
    elif args.roi:
        cmd_roi()
    elif args.history:
        cmd_history()
    elif args.experience:
        cmd_experience(args.scenario)
    elif args.intake:
        cmd_intake()
    elif args.task:
        cmd_run(args.task, brand=args.brand)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
