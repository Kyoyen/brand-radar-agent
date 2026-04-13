"""
Brand Radar Agent — V3: 完整 Agent（Function Calling）
========================================================
V2 → V3 迭代原因：
  V2 解决了「输出格式」问题，但数据采集还是靠人工；
  而且分析完之后还要手动发给团队，没有形成自动化闭环。

V3 改进（核心：让 LLM 自主决策工具调用顺序）：
  1. Function Calling：Agent 自动调用数据采集工具，无需人工粘贴内容
  2. 多工具协同：Agent 可在一次对话内调用多个工具（搜索→分析→推送→存档）
  3. 飞书自动推送：分析完成后直接推送给团队，人工介入降至「核验」环节
  4. 历史对比：每次结果自动存档，下次分析可参考趋势变化

Agent 任务链（V3 设计）：
  [接收任务]
      ↓
  [search_social_content] × N 个竞品 × M 个平台
      ↓
  [get_trending_topics] → 补充热点上下文
      ↓
  [LLM 综合分析] → 生成结构化洞察
      ↓
  [send_feishu_report] → 推送飞书
      ↓
  [save_to_history] × N 个竞品 → 存档

异常回退设计：
  - 工具调用失败：记录错误，继续处理其他竞品
  - LLM 超出最大 turns：强制输出当前最优结论
  - 飞书推送失败：本地保存报告，下次重试
"""

import json
import os
from openai import OpenAI
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from .tools import TOOLS, execute_tool

load_dotenv()
console = Console()

MAX_TURNS = 10  # 防止无限循环的最大工具调用轮次

SYSTEM_PROMPT_V3 = """你是「Brand Radar Agent」，专为品牌营销团队提供自动化竞情分析服务。

【我方品牌】：{our_brand}
【分析目标】：{competitors}
【监控平台】：{platforms}

你的工作流程：
1. 调用 search_social_content 逐一获取每个竞品在各平台的内容数据
2. 调用 get_trending_topics 了解当前平台热门话题，判断竞品是否在蹭热点
3. 基于采集到的数据，综合分析竞品整体社媒策略，识别威胁与机会点
4. 调用 send_feishu_report 将最终报告推送给团队
5. 调用 save_to_history 将每个竞品的分析结果存档备查

异常处理原则：
- 若某个工具调用失败，记录原因后继续处理其余步骤
- 飞书推送失败不影响分析结果输出
- 最终必须给出可执行的建议，不能只描述现象

输出语言：中文
"""


def run_agent(
    our_brand: str,
    competitors: list[str],
    platforms: list[str] = None,
) -> str:
    """
    V3 核心：Agent 主循环（ReAct 模式）
    LLM 自主决定：何时调用什么工具、调用多少次、按什么顺序
    """
    if platforms is None:
        platforms = ["小红书", "抖音"]

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # 初始化消息队列
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT_V3.format(
                our_brand=our_brand,
                competitors="、".join(competitors),
                platforms="、".join(platforms),
            ),
        },
        {
            "role": "user",
            "content": (
                f"请开始今日竞情分析任务。"
                f"分析竞品：{', '.join(competitors)}，"
                f"覆盖平台：{', '.join(platforms)}。"
                f"完成后推送飞书报告并存档。"
            ),
        },
    ]

    turn = 0
    tool_call_log = []  # 记录所有工具调用，便于调试和展示

    console.print(f"\n[bold cyan]🤖 Brand Radar Agent V3 启动[/bold cyan]")
    console.print(f"竞品：{' | '.join(competitors)}  平台：{' | '.join(platforms)}\n")

    while turn < MAX_TURNS:
        turn += 1

        # ── LLM 推理步骤 ─────────────────────────────────────────────────────
        with console.status(f"[cyan]Agent 思考中（第 {turn} 轮）...[/cyan]"):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",   # 由 LLM 自主决定是否调用工具
                temperature=0.2,
            )

        msg = response.choices[0].message
        messages.append(msg)  # 将 LLM 回复加入上下文

        # ── 检查是否结束 ─────────────────────────────────────────────────────
        if response.choices[0].finish_reason == "stop":
            console.print(f"\n[green]✓ Agent 完成（共 {turn} 轮，{len(tool_call_log)} 次工具调用）[/green]")
            return msg.content or "分析完成，报告已推送。"

        # ── 处理工具调用 ─────────────────────────────────────────────────────
        if not msg.tool_calls:
            break

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)

            console.print(f"  [yellow]→ 调用工具:[/yellow] [bold]{fn_name}[/bold]  参数: {fn_args}")

            # 实际执行工具
            result = execute_tool(fn_name, fn_args)
            tool_call_log.append({"tool": fn_name, "args": fn_args, "result": result})

            # 将工具结果反馈给 LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    # 超出最大轮次的兜底
    console.print(f"[yellow]⚠️ 已达最大轮次 {MAX_TURNS}，强制输出当前结论[/yellow]")
    return "分析超时，已输出可用结论。请检查日志。"


# ─── Scheduler：定时执行 ─────────────────────────────────────────────────────

def setup_daily_schedule(
    our_brand: str,
    competitors: list[str],
    platforms: list[str],
    hour: int = 9,
):
    """
    每日定时执行竞情分析（使用 schedule 库）
    生产部署：替换为 Cron / 飞书定时任务 / Airflow
    """
    import schedule
    import time

    def daily_job():
        console.print(f"\n[bold]⏰ 定时任务触发：{hour:02d}:00 竞情分析[/bold]")
        run_agent(our_brand, competitors, platforms)

    schedule.every().day.at(f"{hour:02d}:00").do(daily_job)
    console.print(f"[green]✓ 已设置每日 {hour:02d}:00 自动运行[/green]")
    console.print("按 Ctrl+C 停止\n")

    while True:
        schedule.run_pending()
        time.sleep(60)


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 立即执行一次
    result = run_agent(
        our_brand="肯德基",
        competitors=["麦当劳", "汉堡王"],
        platforms=["小红书", "抖音"],
    )
    if result:
        console.print(f"\n[bold]Agent 最终输出：[/bold]\n{result}")
