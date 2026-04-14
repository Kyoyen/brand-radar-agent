"""
Brand Radar Agent — V3: ReAct Agent
=====================================
V3 核心升级：引入 Function Calling，Agent 自主决定调用什么工具、何时停止。
不再由人工写死执行顺序，而是 LLM 自主规划 → 调用工具 → 观察结果 → 继续推理。

运行方式：
  python -m v3_agent.agent
  python -m v3_agent.agent "分析麦当劳今天在小红书和抖音的内容动态"
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 确保项目根目录在路径里
sys.path.insert(0, str(Path(__file__).parent.parent))
from v3_agent.tools import TOOLS, execute_tool

MAX_TURNS = 10

SYSTEM_PROMPT = """你是一个专业的品牌营销竞品分析 Agent。

你的工作流程：
1. 使用 search_social_content 工具搜索竞品在各平台的内容动态
2. 使用 get_trending_topics 工具了解当前热点，判断竞品是否在蹭热点
3. 综合分析数据，评估竞品的威胁等级
4. 使用 send_feishu_report 工具推送分析报告
5. 使用 save_to_history 工具存档本次分析

分析时重点关注：
- 竞品内容主题和调性变化
- 高互动内容背后的策略
- 对我方品牌的具体威胁
- 可借鉴或需要防御的打法

我方品牌：{our_brand}
"""


def run_agent(task: str, our_brand: str = None) -> str:
    """
    执行竞品分析 Agent 任务。

    Args:
        task:      自然语言任务描述
        our_brand: 我方品牌名（从环境变量读取，可覆盖）

    Returns:
        Agent 最终输出文本
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    brand = our_brand or os.getenv("TARGET_BRAND", "品牌方")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(our_brand=brand)},
        {"role": "user",   "content": task},
    ]

    print(f"\n{'='*60}")
    print(f"Brand Radar V3 — ReAct Agent")
    print(f"任务：{task}")
    print(f"我方品牌：{brand}")
    print(f"{'='*60}\n")

    final_output = ""
    for turn in range(1, MAX_TURNS + 1):
        print(f"[Turn {turn}] 推理中...")

        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )

        msg = response.choices[0].message
        messages.append(msg)

        # 任务完成
        if response.choices[0].finish_reason == "stop":
            final_output = msg.content or "分析完成。"
            print(f"\n✅ 完成（{turn} 轮推理）\n")
            print(final_output)
            break

        # 处理工具调用
        if msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                print(f"  → 调用工具：{name}({args})")

                result = execute_tool(name, args)
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result,
                })

    else:
        final_output = "已达最大轮次限制，任务可能未完全完成。"
        print(f"\n⚠️  {final_output}")

    return final_output


if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "分析麦当劳最近在小红书和抖音的内容策略，评估威胁等级，推送飞书报告"
    run_agent(task)
