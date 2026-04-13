"""
Brand Radar Agent — V1: 基础版
===============================
痛点背景：
  营销团队每周花 3-4 小时手动翻阅竞品的小红书/抖音/微博内容，
  用截图+笔记整理出竞品动态，流程完全依赖人工，效率低且格式不统一。

V1 方案：
  用一个"万能 Prompt"替代手动整理，用户粘贴竞品内容 → GPT 分析 → 输出文字报告

V1 遇到的问题（→ 驱动 V2 迭代）：
  1. 输出格式每次不一致，无法自动化下游处理
  2. 没有品牌上下文，分析结论不够针对性
  3. 内容仍需人工复制粘贴，效率瓶颈未解决
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─── V1 核心 Prompt（第一版，未结构化）─────────────────────────────────────────

SYSTEM_PROMPT_V1 = """你是一位资深品牌营销分析师，擅长分析竞品在社交媒体上的内容策略。
请帮我分析以下竞品的社媒内容，重点关注：内容主题、传播策略、用户互动方式、以及可借鉴的打法。"""

USER_PROMPT_TEMPLATE_V1 = """
竞品品牌：{competitor}
平台：{platform}
内容摘要：
{content}

请提供你的分析。
"""


def analyze_competitor_v1(competitor: str, platform: str, content: str) -> str:
    """
    V1: 最简版本 —— 单次 API 调用，输出纯文字分析
    问题：输出格式随机，无法程序化处理
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_V1},
        {
            "role": "user",
            "content": USER_PROMPT_TEMPLATE_V1.format(
                competitor=competitor,
                platform=platform,
                content=content,
            ),
        },
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
    )

    return response.choices[0].message.content


# ─── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 模拟用户手动粘贴的竞品内容（V1痛点：人工采集）
    sample_content = """
    1. 麦当劳联名 Hello Kitty 玩具套餐，发布3条小红书图文，强调"童年回忆"，
       平均点赞 2000+，评论多为 "好可爱" "好想要"
    2. 主推"麦辣鸡腿堡限时回归"，抖音视频用了"消失的名单"的梗，播放量 150万
    3. 儿童套餐升级，强调"营养均衡"，发布妈妈测评类内容，小红书互动量比平时高 40%
    """

    print("=" * 60)
    print("Brand Radar V1 - 竞品分析（基础版）")
    print("=" * 60)
    print(f"正在分析竞品：麦当劳 | 平台：小红书/抖音")
    print("-" * 60)

    result = analyze_competitor_v1(
        competitor="麦当劳",
        platform="小红书/抖音",
        content=sample_content,
    )

    print(result)
    print("\n" + "=" * 60)
    print("⚠️  V1 问题：输出为非结构化文本，无法自动处理，→ 迭代至 V2")
    print("=" * 60)
