"""
扩展工具集 — 新增场景专用工具
================================
覆盖：
  内容选题 & Brief 生成  → get_brand_calendar, generate_content_brief
  Campaign 复盘          → calculate_campaign_metrics, analyze_channel_performance
  热点预警               → assess_brand_fit, draft_content_hook

所有工具遵循与 v3_agent/tools.py 相同的规范：
  - 接受关键字参数，返回 JSON 字符串
  - Mock 数据结构与真实 API 一致，替换实现不需改接口
"""

import json
from datetime import date, timedelta
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# 内容选题 & Brief 工具
# ══════════════════════════════════════════════════════════════════════════════

def get_brand_calendar(brand: str, weeks_ahead: int = 2) -> dict:
    """
    获取品牌近期营销节点日历
    真实场景：对接企业内部日历系统或飞书文档
    Demo：返回模拟品牌日历
    """
    today = date.today()
    mock_calendar = {
        "brand": brand,
        "period": f"{today} ~ {today + timedelta(weeks=weeks_ahead)}",
        "events": [
            {
                "date": (today + timedelta(days=3)).isoformat(),
                "event": "五一劳动节",
                "type": "节假日",
                "priority": "高",
                "content_angle": "家庭聚餐/打工人放松",
            },
            {
                "date": (today + timedelta(days=7)).isoformat(),
                "event": "新品辣鸡腿堡上市",
                "type": "产品节点",
                "priority": "高",
                "content_angle": "辣度测评/挑战/朋友聚餐",
            },
            {
                "date": (today + timedelta(days=10)).isoformat(),
                "event": "母亲节预热",
                "type": "情感节点",
                "priority": "中",
                "content_angle": "亲情/家庭/感恩",
            },
        ],
        "ongoing_campaigns": ["经典品心智教育季", "会员积分翻倍活动"],
    }
    return mock_calendar


def generate_content_brief(
    brand: str,
    platform: str,
    theme: str,
    target_audience: str,
    count: int = 1,
) -> dict:
    """
    生成结构化内容 Brief
    每个 Brief 包含：选题角度/核心信息/情绪钩子/话题标签/参考形式
    """
    briefs = []
    for i in range(min(count, 5)):
        briefs.append({
            "id": i + 1,
            "platform": platform,
            "theme": theme,
            "title_direction": f"「{theme}」角度{i+1}：从用户真实场景切入",
            "target_audience": target_audience,
            "core_message": f"突出{brand}在「{theme}」场景下的独特价值",
            "emotional_hook": "引发共鸣 → 激发分享欲",
            "content_format": "图文种草" if platform == "小红书" else "15-30秒短视频",
            "suggested_tags": [f"#{theme}", f"#{brand}", "#打卡", "#好物分享"],
            "kpi_target": {
                "likes": "500+",
                "saves": "200+",
                "comments": "50+",
            },
            "do_not": ["硬广感过强", "产品信息超过3处", "强调折扣价格（影响品牌调性）"],
        })
    return {"brand": brand, "generated_count": len(briefs), "briefs": briefs}


# ══════════════════════════════════════════════════════════════════════════════
# Campaign 复盘工具
# ══════════════════════════════════════════════════════════════════════════════

def calculate_campaign_metrics(
    campaign_name: str,
    target_metrics: dict,
    actual_metrics: dict,
) -> dict:
    """
    计算各指标的达成率、差值和同比
    真实场景：对接广告平台 API（巨量引擎/磁力引擎/微博营销）
    """
    results = {}
    for metric, target in target_metrics.items():
        actual = actual_metrics.get(metric, "N/A")
        if actual == "N/A":
            results[metric] = {"target": target, "actual": "未提供", "achievement_rate": "N/A"}
            continue

        # 简单数值解析（真实场景需更完善的解析逻辑）
        try:
            t_val = float(str(target).replace("%", "").replace("万", "0000").replace(",", ""))
            a_val = float(str(actual).replace("%", "").replace("万", "0000").replace(",", ""))
            rate = round(a_val / t_val * 100, 1)
            results[metric] = {
                "target": target,
                "actual": actual,
                "achievement_rate": f"{rate}%",
                "gap": f"{a_val - t_val:+.0f}",
                "status": "✅ 达成" if rate >= 100 else ("⚠️ 接近" if rate >= 80 else "❌ 未达成"),
            }
        except (ValueError, ZeroDivisionError):
            results[metric] = {"target": target, "actual": actual, "achievement_rate": "计算中"}

    overall_achievement = sum(
        1 for v in results.values() if "✅" in str(v.get("status", ""))
    ) / max(len(results), 1) * 100

    return {
        "campaign_name": campaign_name,
        "metrics": results,
        "overall_achievement_rate": f"{round(overall_achievement)}%",
        "summary": "整体表现良好" if overall_achievement >= 80 else "部分指标需要复盘",
    }


def analyze_channel_performance(
    campaign_name: str,
    channels: list = None,
) -> dict:
    """
    按渠道拆解 Campaign 表现差异
    返回各渠道贡献度、CPM/CPE 对比、ROI 分析
    """
    if channels is None:
        channels = ["小红书", "抖音", "微博"]

    mock_performance = {
        "小红书": {"spend_pct": 35, "impression_pct": 28, "engagement_rate": "4.2%", "cpe": "¥1.8", "roi_score": 8},
        "抖音":   {"spend_pct": 45, "impression_pct": 55, "engagement_rate": "3.1%", "cpe": "¥0.9", "roi_score": 9},
        "微博":   {"spend_pct": 20, "impression_pct": 17, "engagement_rate": "1.8%", "cpe": "¥3.2", "roi_score": 5},
    }

    analysis = {}
    for ch in channels:
        if ch in mock_performance:
            perf = mock_performance[ch]
            analysis[ch] = {
                **perf,
                "efficiency": "高效" if perf["roi_score"] >= 8 else ("中等" if perf["roi_score"] >= 6 else "低效"),
                "recommendation": (
                    "建议下次加大预算" if perf["roi_score"] >= 8
                    else ("维持现状，优化素材" if perf["roi_score"] >= 6
                          else "建议削减预算，优化投放策略")
                ),
            }

    best_channel = max(analysis.keys(), key=lambda k: analysis[k]["roi_score"])
    return {
        "campaign_name": campaign_name,
        "channel_breakdown": analysis,
        "best_performing_channel": best_channel,
        "key_insight": f"{best_channel}投放效率最高，建议下次将该渠道预算占比提升至50%+",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 热点预警工具
# ══════════════════════════════════════════════════════════════════════════════

def assess_brand_fit(
    topic: str,
    brand: str,
    brand_tone: str = "年轻/轻松/家庭",
    product_portfolio: list = None,
) -> dict:
    """
    评估热点话题与品牌的契合度
    返回：相关度评分（0-10）、借势可行性、风险提示
    """
    # 简单启发式规则（真实场景：调用 LLM 做语义判断）
    score = 5
    risk = "低"
    angle = ""

    positive_signals = ["美食", "聚餐", "家庭", "朋友", "打卡", "好吃", "探店", "亲子", "假期"]
    negative_signals = ["政治", "事故", "争议", "敏感", "负面", "抵制"]

    for sig in positive_signals:
        if sig in topic:
            score = min(score + 1, 10)
    for sig in negative_signals:
        if sig in topic:
            score = max(score - 3, 0)
            risk = "高"

    if product_portfolio:
        for prod in (product_portfolio or []):
            if any(kw in topic for kw in prod.split()):
                score = min(score + 2, 10)
                angle = f"可结合「{prod}」蹭热"

    return {
        "topic": topic,
        "brand": brand,
        "fit_score": score,
        "risk_level": risk,
        "actionable": score >= 6 and risk != "高",
        "priority": "⚡ 立即行动" if score >= 8 else ("📌 可考虑" if score >= 6 else "⏭️ 跳过"),
        "suggested_angle": angle or f"从品牌调性「{brand_tone}」切入该话题",
        "caution": f"敏感度较高，需品牌公关审核" if risk == "高" else None,
    }


def draft_content_hook(
    topic: str,
    brand: str,
    platform: str,
    fit_assessment: dict = None,
) -> dict:
    """
    为高分热点快速生成内容切入角度和钩子句式
    """
    templates = {
        "小红书": {
            "hook_formats": [
                f"「{topic}」的时候你会选择{brand}吗？",
                f"在{topic}这件事上，{brand}藏着一个很多人不知道的玩法",
                f"今天聊聊{topic}，顺带安利一个{brand}新吃法",
            ],
            "content_type": "图文种草",
            "cta": "评论区告诉我你的选择 👇",
        },
        "抖音": {
            "hook_formats": [
                f"等等！{topic}还有这个玩法？ft.{brand}",
                f"把「{topic}」和{brand}结合，没想到效果这么好",
            ],
            "content_type": "15-30秒短视频，前3秒必须有冲突/悬念",
            "cta": "评论区扣1，看完整版",
        },
    }

    platform_template = templates.get(platform, templates["小红书"])

    return {
        "topic": topic,
        "brand": brand,
        "platform": platform,
        "hook_sentences": platform_template["hook_formats"],
        "recommended_format": platform_template["content_type"],
        "cta": platform_template["cta"],
        "urgency": "48小时内发布效果最佳",
        "estimated_engagement_uplift": "+20-35%（热点借势内容平均涨幅）",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 工具注册
# ══════════════════════════════════════════════════════════════════════════════

EXTENDED_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_brand_calendar",
            "description": "获取品牌近期营销节点日历，包括节假日、产品上市、活动节点，用于内容规划参考。",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string", "description": "品牌名称"},
                    "weeks_ahead": {"type": "integer", "description": "展望未来几周，默认2", "default": 2},
                },
                "required": ["brand"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_content_brief",
            "description": "基于主题和平台生成结构化内容Brief，包含选题角度、情绪钩子、话题标签。",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string"},
                    "platform": {"type": "string", "enum": ["小红书", "抖音", "微博"]},
                    "theme": {"type": "string", "description": "内容主题方向"},
                    "target_audience": {"type": "string", "description": "目标人群描述"},
                    "count": {"type": "integer", "description": "生成Brief数量，默认1", "default": 1},
                },
                "required": ["brand", "platform", "theme", "target_audience"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_campaign_metrics",
            "description": "计算Campaign各指标的目标达成率、差值，输出结构化复盘数据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_name": {"type": "string"},
                    "target_metrics": {"type": "object", "description": "目标指标字典，如{曝光量:'5000万'}"},
                    "actual_metrics": {"type": "object", "description": "实际指标字典"},
                },
                "required": ["campaign_name", "target_metrics", "actual_metrics"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_channel_performance",
            "description": "按渠道拆解Campaign投放表现，计算CPE/ROI，给出各渠道预算优化建议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_name": {"type": "string"},
                    "channels": {"type": "array", "items": {"type": "string"}, "description": "分析的渠道列表"},
                },
                "required": ["campaign_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_brand_fit",
            "description": "评估热点话题与品牌的契合度（0-10分），判断是否值得借势，给出优先级标签。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "热点话题名称"},
                    "brand": {"type": "string"},
                    "brand_tone": {"type": "string", "description": "品牌调性关键词"},
                    "product_portfolio": {"type": "array", "items": {"type": "string"}, "description": "可关联的产品列表"},
                },
                "required": ["topic", "brand"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_content_hook",
            "description": "为高相关度热点生成可直接使用的内容切入句式和发布建议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "brand": {"type": "string"},
                    "platform": {"type": "string", "enum": ["小红书", "抖音", "微博"]},
                },
                "required": ["topic", "brand", "platform"],
            },
        },
    },
]

TOOL_MAP = {
    "get_brand_calendar": get_brand_calendar,
    "generate_content_brief": generate_content_brief,
    "calculate_campaign_metrics": calculate_campaign_metrics,
    "analyze_channel_performance": analyze_channel_performance,
    "assess_brand_fit": assess_brand_fit,
    "draft_content_hook": draft_content_hook,
}


def execute_extended_tool(tool_name: str, arguments: dict) -> str:
    if tool_name not in TOOL_MAP:
        return json.dumps({"error": f"Unknown extended tool: {tool_name}"})
    result = TOOL_MAP[tool_name](**arguments)
    return json.dumps(result, ensure_ascii=False)
