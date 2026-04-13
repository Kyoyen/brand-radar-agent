"""
V3 新增：Function Calling 工具定义
====================================
V3 核心升级：让 Agent 自己决定「何时调用什么工具」，
而不是由代码写死调用顺序。

工具清单：
  1. search_social_content   — 搜索指定竞品在社交平台的内容摘要
  2. get_trending_topics      — 获取当前平台热门话题（判断竞品是否蹭热点）
  3. send_feishu_report       — 将分析结果推送到飞书频道
  4. save_to_history          — 将本次分析存入历史记录（供趋势对比使用）
"""

import json
import os
import httpx
from datetime import datetime, date

# ─── Tool Definitions（OpenAI Function Calling 格式）────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_social_content",
            "description": (
                "搜索指定竞品品牌在指定社交平台最近7天的内容摘要。"
                "返回内容主题、互动数据和典型案例。"
                "当需要获取竞品最新社媒动态时调用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {
                        "type": "string",
                        "description": "要搜索的竞品品牌名称，如「麦当劳」",
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["小红书", "抖音", "微博", "全平台"],
                        "description": "搜索的社交平台",
                    },
                    "days": {
                        "type": "integer",
                        "description": "搜索最近几天的内容，默认7天",
                        "default": 7,
                    },
                },
                "required": ["brand", "platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trending_topics",
            "description": (
                "获取指定平台当前热门话题/趋势词。"
                "用于判断竞品内容是否在蹭热点，以及我方是否有内容机会。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["小红书", "抖音", "微博"],
                        "description": "要查询热门话题的平台",
                    },
                    "category": {
                        "type": "string",
                        "description": "话题类别，如「餐饮美食」「生活方式」，不填则返回全品类",
                    },
                },
                "required": ["platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_feishu_report",
            "description": (
                "将竞品分析报告推送到飞书群机器人。"
                "当分析完成、需要通知团队时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "报告标题",
                    },
                    "summary": {
                        "type": "string",
                        "description": "报告摘要，100字以内",
                    },
                    "key_findings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关键发现列表，3-5条",
                    },
                    "action_items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "建议行动列表，2-3条",
                    },
                    "threat_level": {
                        "type": "string",
                        "enum": ["高威胁", "中等威胁", "低威胁", "可借鉴"],
                        "description": "整体威胁等级",
                    },
                },
                "required": ["title", "summary", "key_findings", "action_items", "threat_level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_to_history",
            "description": (
                "将本次竞品分析结果保存到历史记录中，"
                "用于下次分析时进行趋势对比（判断竞品是否在加速/减速）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string", "description": "竞品品牌"},
                    "date": {"type": "string", "description": "分析日期 YYYY-MM-DD"},
                    "threat_level": {"type": "string"},
                    "key_themes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "本次主要内容主题",
                    },
                    "engagement_summary": {
                        "type": "string",
                        "description": "互动数据概况",
                    },
                },
                "required": ["brand", "date", "threat_level", "key_themes"],
            },
        },
    },
]


# ─── Tool Implementations（实际执行逻辑）──────────────────────────────────────

def search_social_content(brand: str, platform: str, days: int = 7) -> dict:
    """
    真实场景：对接小红书/抖音数据服务商 API（如蝉妈妈、新红等）
    Demo 场景：返回模拟数据，结构与真实 API 一致

    替换说明：将 mock_data 部分替换为实际 API 调用即可，接口不变。
    """
    mock_data = {
        ("麦当劳", "小红书"): {
            "brand": "麦当劳", "platform": "小红书", "days": days,
            "total_posts": 47, "total_engagement": 128000,
            "top_themes": [
                {"theme": "联名周边", "posts": 18, "avg_likes": 3200, "sample": "Hello Kitty套餐开箱，带#童年回忆话题"},
                {"theme": "限时产品回归", "posts": 12, "avg_likes": 2800, "sample": "麦辣鸡腿堡限时回归倒计时"},
                {"theme": "儿童套餐升级", "posts": 9, "avg_likes": 1900, "sample": "妈妈带娃探店，主打营养均衡"},
            ],
            "tone": "温情 + 童趣 + 怀旧",
            "kol_count": 23,
            "paid_posts_ratio": "约40%",
        },
        ("麦当劳", "抖音"): {
            "brand": "麦当劳", "platform": "抖音", "days": days,
            "total_posts": 31, "total_engagement": 2400000,
            "top_themes": [
                {"theme": "热梗蹭热点", "posts": 15, "avg_views": 850000, "sample": "用「消失的名单」梗推麦辣鸡腿堡，播放150万"},
                {"theme": "挑战赛", "posts": 8, "avg_views": 320000, "sample": "#我的麦门时刻 话题挑战"},
            ],
            "tone": "年轻化 + 幽默 + 互动强",
            "kol_count": 15,
            "paid_posts_ratio": "约60%",
        },
        ("汉堡王", "小红书"): {
            "brand": "汉堡王", "platform": "小红书", "days": days,
            "total_posts": 19, "total_engagement": 42000,
            "top_themes": [
                {"theme": "火焰烤制差异化", "posts": 11, "avg_likes": 980, "sample": "真火烤制不加香精，健康理性内容"},
                {"theme": "辣味挑战", "posts": 6, "avg_likes": 1200, "sample": "变态辣挑战打卡"},
            ],
            "tone": "理性 + 健康 + 差异化",
            "kol_count": 8,
            "paid_posts_ratio": "约25%",
        },
    }

    key = (brand, platform)
    if key in mock_data:
        return mock_data[key]

    # 默认返回低声量数据
    return {
        "brand": brand, "platform": platform, "days": days,
        "total_posts": 5, "total_engagement": 8000,
        "top_themes": [{"theme": "常规促销", "posts": 5, "avg_likes": 600, "sample": "节假日促销活动"}],
        "tone": "平淡",
        "kol_count": 2,
        "paid_posts_ratio": "约10%",
    }


def get_trending_topics(platform: str, category: str = None) -> dict:
    """获取热门话题（mock 真实数据结构）"""
    topics = {
        "小红书": ["#五一出游计划", "#春日野餐", "#亲子周末", "#下午茶打卡", "#新中式美食"],
        "抖音": ["#五一特辑", "#美食探店", "#打工人续命", "#和朋友去吃饭", "#解压神器"],
        "微博": ["#五一假期", "#餐厅推荐", "#亲子活动", "#网红打卡地"],
    }
    return {
        "platform": platform,
        "date": date.today().isoformat(),
        "trending": topics.get(platform, []),
        "category": category or "全品类",
        "tip": "建议结合「亲子」「出游」场景策划五一内容",
    }


def send_feishu_report(
    title: str,
    summary: str,
    key_findings: list,
    action_items: list,
    threat_level: str,
) -> dict:
    """
    推送到飞书群机器人
    真实场景：调用飞书 Webhook，发送 card 消息
    Demo 场景：打印内容 + 模拟成功响应
    """
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")

    threat_color = {
        "高威胁": "red", "中等威胁": "orange",
        "低威胁": "green", "可借鉴": "blue",
    }.get(threat_level, "grey")

    # 飞书 Card 消息格式
    card_payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"🔍 {title}"},
                "template": threat_color,
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**摘要**\n{summary}"}},
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**关键发现**\n" + "\n".join(f"• {f}" for f in key_findings),
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**建议行动**\n" + "\n".join(f"✅ {a}" for a in action_items),
                    },
                },
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"Brand Radar Agent · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                    ],
                },
            ],
        },
    }

    if webhook_url:
        try:
            resp = httpx.post(webhook_url, json=card_payload, timeout=10)
            return {"status": "sent", "feishu_response": resp.json()}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    else:
        # Demo 模式：打印卡片内容
        print("\n" + "=" * 50)
        print(f"📨 [飞书推送模拟] {title}")
        print(f"威胁等级：{threat_level}")
        print(f"摘要：{summary}")
        print("关键发现：")
        for f in key_findings:
            print(f"  • {f}")
        print("建议行动：")
        for a in action_items:
            print(f"  ✅ {a}")
        print("=" * 50 + "\n")
        return {"status": "demo_printed", "message": "设置 FEISHU_WEBHOOK_URL 后可真实推送"}


def save_to_history(
    brand: str,
    date: str,
    threat_level: str,
    key_themes: list,
    engagement_summary: str = "",
) -> dict:
    """将分析结果追加到本地 JSON 历史文件"""
    history_file = "competitor_history.json"
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    except FileNotFoundError:
        history = []

    history.append({
        "brand": brand,
        "date": date,
        "threat_level": threat_level,
        "key_themes": key_themes,
        "engagement_summary": engagement_summary,
    })

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    return {"status": "saved", "total_records": len(history)}


# ─── Tool dispatcher ──────────────────────────────────────────────────────────

TOOL_MAP = {
    "search_social_content": search_social_content,
    "get_trending_topics": get_trending_topics,
    "send_feishu_report": send_feishu_report,
    "save_to_history": save_to_history,
}


def execute_tool(tool_name: str, arguments: dict) -> str:
    """统一工具调用入口，返回 JSON 字符串供 Agent 消费"""
    if tool_name not in TOOL_MAP:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    result = TOOL_MAP[tool_name](**arguments)
    return json.dumps(result, ensure_ascii=False)
