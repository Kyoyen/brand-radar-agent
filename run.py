"""
Brand Radar Agent — 统一入口
==============================
用法：
  python run.py "为下周瑞幸咖啡周企划会整理咖啡品类观察"
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

DEFAULT_WEEKLY_SOURCE_PACK = ROOT / "data/replay/coffee-week-2026-09-07/manifest.json"


# ── 环境检查 ────────────────────────────────────────────────────────────────

def check_env(require_api: bool = False):
    """检查 Provider/Key 是否满足当前命令，不读取或打印 Key 内容。"""
    provider = os.getenv("LLM_PROVIDER", "deepseek").lower()
    key_map = {
        "openai":    ("OPENAI_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY",),
        "deepseek":  ("DEEPSEEK_API_KEY",),
        "moonshot":  ("MOONSHOT_API_KEY",),
        "zhipu":     ("ZHIPUAI_API_KEY", "ZHIPU_API_KEY"),
    }
    if provider not in key_map:
        print(f"  [错误] 不支持的 LLM_PROVIDER: {provider}")
        return False
    env_vars = key_map[provider]
    configured_var = next((name for name in env_vars if os.getenv(name)), None)
    if configured_var:
        print(f"  [配置] Provider: {provider} | Key: 已配置（{configured_var}）")
    elif require_api:
        accepted = " 或 ".join(env_vars)
        print(f"  [错误] --require-api 需要本机配置 {accepted}；真实模式已停止，未读取材料。")
        return False
    else:
        print(f"  [配置] Provider: {provider} | Key: 未配置 → 仅允许明确标记的 Mock 烟雾测试")
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


def cmd_weekly(source_pack: str, require_api: bool, task: str | None = None) -> int:
    from framework import AgentRunner
    from framework.brand_radar_report import render_weekly_report
    from framework.brand_radar_output import BrandRadarValidationError
    from framework.llm_client import LLMConfigurationError, LLMRequestError
    from scenarios.brand_radar_weekly import WeeklyPipelineError, WeeklySourcePackError

    source_pack_path = Path(source_pack).expanduser()
    if not source_pack_path.is_absolute():
        source_pack_path = ROOT / source_pack_path

    try:
        runner = AgentRunner(require_api=require_api)
        output, output_path = runner.run_weekly(
            source_pack=source_pack_path,
            task_description=task or "",
        )
    except LLMConfigurationError as exc:
        print(f"\n[失败] 真实模型配置不完整：{exc}")
        return 2
    except LLMRequestError as exc:
        print(f"\n[失败] 真实模型调用失败：{exc}")
        print("未降级为 Mock，未生成伪业务结果。")
        return 3
    except WeeklySourcePackError as exc:
        print(f"\n[失败] Replay 观察包无效：{exc}")
        return 4
    except WeeklyPipelineError as exc:
        print(f"\n[失败] 周企划阶段链中断：{exc}")
        return 5
    except BrandRadarValidationError as exc:
        print(f"\n[失败] Brand Radar 结果校验未通过：{exc}")
        for issue in exc.issues[:8]:
            print(
                f"  - {issue.location}: {issue.message} "
                f"({issue.type})"
            )
        return 6
    except Exception as exc:
        print(f"\n[失败] 周企划未完成（{type(exc).__name__}）。未生成结果，也未降级为 Mock。")
        return 7

    data = output.model_dump(mode="json")
    try:
        report_path = render_weekly_report(output, json_path=output_path)
    except Exception as exc:
        print(f"\n[失败] 业务结果已保存，但周会版报告生成失败（{type(exc).__name__}）。")
        print(f"可追溯结果仍可复查：{output_path}")
        return 8
    info = data["run_info"]
    review = data["human_review"]
    print("\n✓ Brand Radar weekly 已生成并通过专用校验")
    print(f"  模式：{info['mode'].upper()}")
    print(f"  Provider / 模型：{info['provider']} / {info['model']}")
    print(f"  材料包：{info['source_pack']}")
    print(f"  可追溯结果：{output_path}")
    print(f"  周会版报告：{report_path}")
    print(f"  情报卡 / Brief：{len(data['intelligence_cards'])} / {len(data['briefs'])}")
    print(f"  控制点：{review['status']}；未发送飞书、未发布、未投放、未改预算")
    if info["mode"] == "mock":
        print("  [MOCK] 仅证明程序链路可运行，不能作为真实模型业务验收。")
    return 0


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
  python run.py "为下周瑞幸咖啡周企划会整理咖啡品类观察"
  python run.py "生成关于夏日饮品的内容选题" --brand 瑞幸咖啡
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
    parser.add_argument("--weekly",      action="store_true", help="运行 Brand Radar 周企划单场景")
    parser.add_argument(
        "--source-pack",
        default=str(DEFAULT_WEEKLY_SOURCE_PACK.relative_to(ROOT)),
        help="周企划 Replay manifest 路径",
    )
    parser.add_argument(
        "--require-api",
        action="store_true",
        help="要求真实模型；缺 Key 或模型失败时立即停止，绝不降级 Mock",
    )

    args = parser.parse_args()

    if args.require_api and not args.weekly:
        parser.error("--require-api 目前只与 --weekly 一起使用")
    if args.weekly and any((args.list, args.roi, args.history, args.experience, args.intake)):
        parser.error("--weekly 不能与 --list/--roi/--history/--experience/--intake 同时使用")

    print("\n🔍 Brand Radar Agent OS")
    print("─" * 40)

    if not check_env(require_api=args.weekly and args.require_api):
        return 2

    if args.weekly:
        return cmd_weekly(args.source_pack, args.require_api, task=args.task)
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
