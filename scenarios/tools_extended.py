"""
Extended Tools — 扩展工具集
==============================
为 campaign_debrief、content_brief、trend_alert 等场景提供专用工具。
生产环境：将每个函数中的 mock 数据替换为真实 API 调用即可。

工具列表：
  - get_campaign_data        竞品 Campaign 历史数据
  - analyze_sentiment        评论情感分析（关键词驱动）
  - generate_content_brief   基于热点生成内容选题方案
  - get_platform_trending    获取平台实时热点榜单
  - send_email_report        邮件发送报告（Feishu 替代）
"""

import json
from datetime import date, timedelta
import random

# ── 工具定义（OpenAI Function Calling 格式）────────────────────────────────

EXTENDED_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_campaign_data",
            "description": "获取指定品牌在某个时间段内的 Campaign 表现数据，用于复盘分析",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand":      {"type": "string", "description": "品牌名称"},
                    "campaign":   {"type": "string", "description": "Campaign 名称或主题"},
                    "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                    "end_date":   {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                },
                "required": ["brand", "campaign"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_sentiment",
            "description": "对指定品牌的社媒内容进行情感分析，返回正负中性分布及高频关键词",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand":    {"type": "string", "description": "品牌名称"},
                    "platform": {"type": "string", "description": "平台：xiaohongshu / douyin / weibo"},
                    "days":     {"type": "integer", "description": "分析最近几天的内容，默认 7"},
                },
                "required": ["brand"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_content_brief",
            "description": "基于热点话题和品牌定位，生成可执行的内容选题方案（含角度、格式、钩子）",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand":       {"type": "string", "description": "品牌名称"},
                    "topic":       {"type": "string", "description": "热点话题或关键词"},
                    "platform":    {"type": "string", "description": "目标平台"},
                    "count":       {"type": "integer", "description": "生成选题数量，默认 5"},
                    "tone":        {"type": "string", "description": "内容基调：professional / casual / humorous"},
                },
                "required": ["brand", "topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_platform_trending",
            "description": "获取指定平台当前热点榜单，可过滤特定类目",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "平台：xiaohongshu / douyin / weibo / bilibili"},
                    "category": {"type": "string", "description": "类目过滤：food / beauty / lifestyle / finance / all（默认）"},
                    "limit":    {"type": "integer", "description": "返回条数，默认 10"},
                },
                "required": ["platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email_report",
            "description": "将报告以邮件格式发送给指定收件人（Feishu 不可用时的备选）",
            "parameters": {
                "type": "object",
                "properties": {
                    "to":      {"type": "string", "description": "收件人邮箱"},
                    "subject": {"type": "string", "description": "邮件主题"},
                    "body":    {"type": "string", "description": "邮件正文（Markdown 格式）"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]


# ── 工具执行 ───────────────────────────────────────────────────────────────

def execute_extended_tool(name: str, args: dict) -> str:
    handlers = {
        "get_campaign_data":     _get_campaign_data,
        "analyze_sentiment":     _analyze_sentiment,
        "generate_content_brief": _generate_content_brief,
        "get_platform_trending": _get_platform_trending,
        "send_email_report":     _send_email_report,
    }
    fn = handlers.get(name)
    if not fn:
        return json.dumps({"error": f"工具 {name} 未找到"}, ensure_ascii=False)
    return fn(**args)


# ── 各工具实现（当前为 mock，生产替换此区域）───────────────────────────────

def _get_campaign_data(brand: str, campaign: str, start_date: str = None, end_date: str = None) -> str:
    """
    生产替换：接入品牌内部 Campaign 数据库 / 数据看板 API
    """
    today = date.today()
    mock = {
        "brand": brand,
        "campaign": campaign,
        "period": f"{start_date or (today - timedelta(days=30)).isoformat()} ~ {end_date or today.isoformat()}",
        "kpis": {
            "total_posts":     random.randint(80, 200),
            "total_reach":     f"{random.randint(200, 800)}万",
            "avg_engagement":  f"{random.uniform(3.5, 8.2):.1f}%",
            "top_content_type": random.choice(["短视频", "图文", "直播"]),
            "cost_per_engage": f"¥{random.uniform(0.3, 1.2):.2f}",
        },
        "highlights": [
            f"#{brand}_{campaign}话题 累计阅读 {random.randint(1000, 5000)}万",
            f"UGC 自发传播率 {random.randint(15, 40)}%，超行业均值",
            f"转化率峰值出现在投放第 {random.randint(3, 7)} 天",
        ],
        "weak_points": [
            "30岁以上用户触达率不足",
            "华南地区曝光偏低",
        ],
        "note": "[MOCK] 生产环境：替换为品牌数据平台 API 或数据库查询"
    }
    return json.dumps(mock, ensure_ascii=False, indent=2)


def _analyze_sentiment(brand: str, platform: str = "xiaohongshu", days: int = 7) -> str:
    """
    生产替换：接入 NLP 情感分析服务 / 数说故事 / 新红等数据平台
    """
    mock = {
        "brand": brand, "platform": platform, "days_analyzed": days,
        "sentiment": {"positive": 58, "neutral": 31, "negative": 11},
        "top_positive_keywords": ["好吃", "性价比高", "服务好", "颜值高", "回购"],
        "top_negative_keywords": ["等位久", "分量少", "价格贵"],
        "risk_flag": "negative占比 11%，处于健康区间（阈值 15%）",
        "note": "[MOCK] 生产环境：替换为情感分析 API（如 DataStory / 文心 NLP）"
    }
    return json.dumps(mock, ensure_ascii=False, indent=2)


def _generate_content_brief(brand: str, topic: str, platform: str = "xiaohongshu",
                             count: int = 5, tone: str = "casual") -> str:
    """
    生产替换：调用 LLM 生成 + 结合平台热词数据优化
    此处为静态 mock，实际应动态生成。
    """
    briefs = [
        {
            "title": f"「{topic}」{brand}的3个反常识玩法",
            "angle": "反预期，引发讨论",
            "hook": f"大家都说{topic}要这样做，但{brand}偏偏反着来...",
            "format": "图文 6-9张",
            "estimated_engagement": "高",
        },
        {
            "title": f"在{topic}里找到{brand}的正确打开方式",
            "angle": "场景植入，生活化",
            "hook": f"你有没有试过在{topic}的时候搭配{brand}？",
            "format": "短视频 30-60秒",
            "estimated_engagement": "中高",
        },
    ]
    return json.dumps({"brand": brand, "topic": topic, "platform": platform,
                       "briefs": briefs[:count],
                       "note": "[MOCK] 生产环境：动态调用 LLM 生成并结合热词数据"
                       }, ensure_ascii=False, indent=2)


def _get_platform_trending(platform: str, category: str = "all", limit: int = 10) -> str:
    """
    生产替换：接入各平台热点 API / 第三方数据服务（新红、卡思数据等）
    """
    topics = [
        {"rank": 1, "topic": "夏日轻食", "heat": "9.8万讨论", "trend": "↑快速上升"},
        {"rank": 2, "topic": "职场穿搭", "heat": "7.2万讨论", "trend": "→平稳"},
        {"rank": 3, "topic": "露营好物", "heat": "6.1万讨论", "trend": "↑上升"},
        {"rank": 4, "topic": "早C晚A护肤", "heat": "5.8万讨论", "trend": "↓下降"},
        {"rank": 5, "topic": "家居改造", "heat": "4.9万讨论", "trend": "→平稳"},
    ]
    return json.dumps({
        "platform": platform, "category": category,
        "snapshot_time": date.today().isoformat(),
        "trending": topics[:limit],
        "note": "[MOCK] 生产环境：替换为平台官方 API 或第三方数据服务"
    }, ensure_ascii=False, indent=2)


def _send_email_report(to: str, subject: str, body: str) -> str:
    """
    生产替换：接入 SMTP / SendGrid / 企业邮件 API
    """
    print(f"\n  [邮件模拟发送] To: {to} | 主题: {subject}")
    return json.dumps({
        "status": "mock_sent",
        "to": to, "subject": subject,
        "preview": body[:100] + "...",
        "note": "[MOCK] 生产环境：替换为 SMTP 或 SendGrid API 调用"
    }, ensure_ascii=False)
