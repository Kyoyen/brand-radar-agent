"""
Brand Radar Agent — V2: 结构化输出版
======================================
V1 → V2 迭代原因：
  V1 输出的是自由文本，每次格式不一样，无法自动汇总多个竞品、无法接入下游系统。
  团队收到报告后还要二次人工整理，效率收益有限。

V2 改进：
  1. 引入 Pydantic Schema，强制 GPT 输出标准化 JSON（Structured Output）
  2. 加入「我方品牌上下文」参数，让分析结论更有针对性
  3. 支持多竞品批量分析，结果可对比

V2 仍存在的问题（→ 驱动 V3 迭代）：
  1. 内容仍需人工复制粘贴，采集环节没有自动化
  2. 报告只能本地查看，无法自动推送给团队
  3. 无法定时执行，还是一次性任务
"""

import os
import json
from datetime import date
from openai import OpenAI
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from .schemas import CompetitorBrief, ThreatLevel

load_dotenv()
console = Console()


# ─── V2 改进：带品牌上下文的 System Prompt ────────────────────────────────────

SYSTEM_PROMPT_V2 = """你是一位服务于「{our_brand}」的品牌竞情分析师。

你的分析需要从「{our_brand}」的视角出发：
- 识别竞品哪些打法对我方构成威胁
- 发现可以借鉴或差异化的机会点
- 给出具体可执行的应对建议

请严格按照 JSON Schema 输出结构化报告，不要输出其他内容。"""

USER_PROMPT_V2 = """
请分析以下竞品社媒内容，输出标准竞情简报：

竞品品牌：{competitor}
分析日期：{today}
内容摘要：
{content}

要求：按 Schema 输出完整 JSON，threat_level 必须从 [高威胁, 中等威胁, 低威胁, 可借鉴] 中选择。
"""


def analyze_competitor_v2(
    competitor: str,
    content: str,
    our_brand: str = "肯德基",
) -> CompetitorBrief:
    """
    V2: 结构化输出 —— 使用 OpenAI Structured Output 强制返回 JSON
    返回 Pydantic 对象，可直接程序化处理
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT_V2.format(our_brand=our_brand),
            },
            {
                "role": "user",
                "content": USER_PROMPT_V2.format(
                    competitor=competitor,
                    today=date.today().isoformat(),
                    content=content,
                ),
            },
        ],
        response_format=CompetitorBrief,   # ← V2 关键：强制结构化
        temperature=0.3,                    # ← 降低随机性，保证格式稳定
    )

    return response.choices[0].message.parsed


def batch_analyze(
    competitors_data: dict[str, str],
    our_brand: str = "肯德基",
) -> list[CompetitorBrief]:
    """
    V2 新增：批量分析多个竞品，返回可排序/筛选的列表
    """
    results = []
    for competitor, content in competitors_data.items():
        console.print(f"[cyan]正在分析：{competitor}...[/cyan]")
        brief = analyze_competitor_v2(competitor, content, our_brand)
        results.append(brief)

    # 按威胁等级排序（高威胁优先）
    threat_order = {
        ThreatLevel.HIGH: 0,
        ThreatLevel.MEDIUM: 1,
        ThreatLevel.OPPORTUNITY: 2,
        ThreatLevel.LOW: 3,
    }
    results.sort(key=lambda x: threat_order.get(x.threat_level, 99))
    return results


def display_brief(brief: CompetitorBrief):
    """用 Rich 格式化展示竞品简报"""
    threat_colors = {
        ThreatLevel.HIGH: "red",
        ThreatLevel.MEDIUM: "yellow",
        ThreatLevel.LOW: "green",
        ThreatLevel.OPPORTUNITY: "blue",
    }
    color = threat_colors.get(brief.threat_level, "white")

    console.print(
        Panel(
            f"[bold]{brief.competitor_name}[/bold]  |  "
            f"威胁等级：[{color}]{brief.threat_level.value}[/{color}]\n\n"
            f"[italic]{brief.overall_strategy}[/italic]",
            title="竞情简报",
            border_style=color,
        )
    )

    # 核心信息
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("维度", width=12)
    table.add_column("内容")
    table.add_row("核心信息", "  |  ".join(brief.core_messaging))
    table.add_row(
        "建议行动",
        "\n".join(f"• {r}" for r in brief.actionable_recommendations),
    )
    if brief.watch_out:
        table.add_row("⚠️ 预警", brief.watch_out)
    console.print(table)


# ─── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample_data = {
        "麦当劳": """
            小红书：联名 Hello Kitty 套餐，3条图文，均破2000赞，评论以"好可爱""童年回忆"为主
            抖音：麦辣鸡腿堡限时回归，用"消失的名单"梗，播放量150万
            微博：儿童套餐升级，妈妈测评内容，互动比平均高40%
        """,
        "汉堡王": """
            小红书：主打"火焰烤制"差异化，强调不加人工香精，内容偏向健康理性风格
            抖音：联合搞笑博主，辣味挑战赛，播放量80万，评论区以打卡为主
            微博：活动较少，主要转发节假日促销，整体声量弱
        """,
    }

    console.print("\n[bold green]Brand Radar V2 — 结构化竞品分析[/bold green]\n")
    briefs = batch_analyze(sample_data, our_brand="肯德基")

    for brief in briefs:
        display_brief(brief)
        console.print()

    # 导出 JSON（可接入下游系统）
    output = [b.model_dump() for b in briefs]
    with open("v2_output.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    console.print("[green]✓ 已导出结构化 JSON: v2_output.json[/green]")
    console.print("\n[yellow]⚠️  V2 问题：内容采集仍需人工，报告无法自动推送 → 迭代至 V3[/yellow]")
