"""
Real Tools — 真实 API 工具集
===============================
免 auth、免付费、可在沙盒外直接跑通的真实数据源。
作为 Mock 工具的替代/补充，验证整套框架在真实数据上工作。

已接入：
  - get_google_trends    Google Trends 实时热度（pytrends）
  - get_hackernews_top   HackerNews 热门 top 榜（官方 JSON）
  - get_weibo_hot        微博热搜（公开 RSS / 第三方聚合）
  - fetch_url_content    通用 URL 抓取（requests + readability）

未接入但有路径（见 docs/api_integration.md）：
  - 小红书 / 抖音：无官方开放 API，需第三方付费服务
  - 微信指数 / 百度指数：需企业资质
"""

import json
import os
from datetime import datetime

REAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_google_trends",
            "description": "查询 Google Trends 上某关键词的近期热度趋势和相关上升话题。"
                           "适合海外品牌监控和跨境内容选题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords":  {"type": "array", "items": {"type": "string"},
                                   "description": "关键词列表，最多 5 个"},
                    "geo":       {"type": "string", "description": "地区代码，如 'US' / 'JP' / 'GB'，默认 'US'"},
                    "timeframe": {"type": "string", "description": "时间窗，如 'now 7-d' / 'today 1-m'，默认 'now 7-d'"},
                },
                "required": ["keywords"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hackernews_top",
            "description": "获取 HackerNews 当前热门话题 Top N，含标题、评分、评论数和 URL。"
                           "适合科技/创业类品牌做内容选题和趋势监控。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit":   {"type": "integer", "description": "返回条数，默认 10，最大 30"},
                    "min_score": {"type": "integer", "description": "最低分阈值，默认 50"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weibo_hot",
            "description": "获取微博热搜榜（来自公开聚合源），含话题名、热度值和分类。"
                           "国内营销监控基础数据。注意：来源为第三方镜像，可能限频。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回条数，默认 20，最大 50"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url_content",
            "description": "抓取任意公开 URL 的正文内容（自动去除导航/广告）。"
                           "用于读取竞品发布的公关文、博客、新闻报道等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url":         {"type": "string", "description": "完整 URL"},
                    "max_chars":   {"type": "integer", "description": "返回字符上限，默认 3000"},
                },
                "required": ["url"],
            },
        },
    },
]


# ── 执行入口 ───────────────────────────────────────────────────────────

def execute_real_tool(name: str, args: dict) -> str:
    handlers = {
        "get_google_trends":  _get_google_trends,
        "get_hackernews_top": _get_hackernews_top,
        "get_weibo_hot":      _get_weibo_hot,
        "fetch_url_content":  _fetch_url_content,
    }
    fn = handlers.get(name)
    if not fn:
        return json.dumps({"error": f"工具 {name} 未注册"}, ensure_ascii=False)
    try:
        return fn(**args)
    except ImportError as e:
        return json.dumps({
            "error": f"缺少依赖：{e}",
            "fix": "pip install -r requirements.txt",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"{type(e).__name__}: {e}",
            "tool": name, "args": args,
        }, ensure_ascii=False)


# ── 各工具实现 ─────────────────────────────────────────────────────────

def _get_google_trends(keywords: list, geo: str = "US", timeframe: str = "now 7-d") -> str:
    """
    依赖：pip install pytrends
    数据源：Google Trends（免费、无需 auth）
    """
    from pytrends.request import TrendReq
    py = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
    py.build_payload(keywords[:5], geo=geo, timeframe=timeframe)

    interest = py.interest_over_time()
    related  = {}
    try:
        related_dict = py.related_queries()
        for kw, d in related_dict.items():
            if d and "rising" in d and d["rising"] is not None:
                related[kw] = d["rising"].head(5).to_dict("records")
    except Exception:
        pass

    result = {
        "source": "google_trends",
        "snapshot_at": datetime.now().isoformat(timespec="seconds"),
        "geo": geo, "timeframe": timeframe,
        "keywords": keywords,
        "interest_summary": {
            kw: {
                "avg":  float(interest[kw].mean()) if kw in interest.columns else None,
                "peak": int(interest[kw].max())   if kw in interest.columns else None,
                "latest": int(interest[kw].iloc[-1]) if kw in interest.columns and len(interest) else None,
            } for kw in keywords
        },
        "rising_related": related,
    }
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


def _get_hackernews_top(limit: int = 10, min_score: int = 50) -> str:
    """
    数据源：HackerNews 官方 Firebase API（完全免费，无 rate limit 实际限制）
    """
    import requests
    limit = min(limit, 30)

    ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()
    items = []
    for story_id in ids[: limit * 2]:
        try:
            s = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=5).json()
            if s and s.get("score", 0) >= min_score and s.get("type") == "story":
                items.append({
                    "title": s.get("title"),
                    "score": s.get("score"),
                    "comments": s.get("descendants", 0),
                    "url": s.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                    "by": s.get("by"),
                })
            if len(items) >= limit:
                break
        except Exception:
            continue

    return json.dumps({
        "source": "hackernews",
        "snapshot_at": datetime.now().isoformat(timespec="seconds"),
        "filter": {"min_score": min_score, "limit": limit},
        "items": items,
    }, ensure_ascii=False, indent=2)


def _get_weibo_hot(limit: int = 20) -> str:
    """
    数据源：微博无官方开放热搜 API。这里使用第三方聚合（vvhan.com 等公开镜像）。
    生产环境建议：申请微博企业开放平台账号 / 接入第三方数据服务（新浪舆情通等）。
    """
    import requests
    limit = min(limit, 50)

    sources = [
        "https://api.vvhan.com/api/hotlist/wbHot",
        "https://api.tangdouz.com/a/wbrs.php",
    ]
    for url in sources:
        try:
            r = requests.get(url, timeout=8)
            data = r.json()
            items = data.get("data") or data.get("subjects") or data
            if isinstance(items, list) and items:
                normalized = [{
                    "rank":  i + 1,
                    "title": (it.get("title") or it.get("name") or it.get("word") or ""),
                    "hot":   (it.get("hot")   or it.get("num")  or it.get("value") or ""),
                    "url":   it.get("url", ""),
                } for i, it in enumerate(items[:limit])]
                return json.dumps({
                    "source": f"weibo_via_{url.split('/')[2]}",
                    "snapshot_at": datetime.now().isoformat(timespec="seconds"),
                    "items": normalized,
                    "note": "数据来自第三方聚合，生产环境请接入官方/付费服务",
                }, ensure_ascii=False, indent=2)
        except Exception:
            continue

    return json.dumps({
        "error": "所有微博热搜源均不可用，建议接入付费数据服务",
        "see": "docs/api_integration.md",
    }, ensure_ascii=False)


def _fetch_url_content(url: str, max_chars: int = 3000) -> str:
    """
    数据源：直接抓取公开网页正文。
    依赖：requests + readability-lxml（可选，缺失则降级为纯文本提取）
    """
    import requests
    headers = {"User-Agent": "Mozilla/5.0 (BrandRadarAgent/1.0)"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    html = r.text

    text = ""
    try:
        from readability import Document
        from bs4 import BeautifulSoup
        doc = Document(html)
        text = BeautifulSoup(doc.summary(), "html.parser").get_text("\n", strip=True)
    except ImportError:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)

    if len(text) > max_chars:
        text = text[:max_chars] + "...[truncated]"

    return json.dumps({
        "source": "web_fetch",
        "url": url,
        "snapshot_at": datetime.now().isoformat(timespec="seconds"),
        "content": text,
        "char_count": len(text),
    }, ensure_ascii=False, indent=2)
