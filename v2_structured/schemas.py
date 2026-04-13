"""
V2 新增：结构化数据模型
========================
用 Pydantic 定义输出 Schema，强制 GPT 输出可程序化处理的 JSON。
解决 V1 的"输出格式随机"问题。
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ThreatLevel(str, Enum):
    HIGH = "高威胁"
    MEDIUM = "中等威胁"
    LOW = "低威胁"
    OPPORTUNITY = "可借鉴"


class ContentTheme(BaseModel):
    theme_name: str = Field(description="内容主题名称，如：亲子联名、情绪营销、限时回归")
    frequency: int = Field(description="该主题出现频次（估计）", ge=0)
    avg_engagement: str = Field(description="平均互动数据，如 '点赞 2000+，评论 150'")
    representative_example: str = Field(description="最典型的案例描述")


class PlatformInsight(BaseModel):
    platform: str = Field(description="平台名称：小红书/抖音/微博")
    main_content_type: str = Field(description="主要内容形态：图文/短视频/话题挑战等")
    posting_frequency: str = Field(description="发布频率估计，如 '每周3-5条'")
    top_themes: list[ContentTheme] = Field(description="该平台上的主要内容主题，最多3个")
    tone_style: str = Field(description="内容调性，如：轻松幽默、亲情温暖、年轻潮流")


class CompetitorBrief(BaseModel):
    """竞品分析简报 — V2 结构化输出"""

    competitor_name: str = Field(description="竞品品牌名称")
    analysis_date: str = Field(description="分析日期，格式 YYYY-MM-DD")
    overall_strategy: str = Field(
        description="竞品整体社媒策略一句话总结（不超过50字）"
    )
    platform_insights: list[PlatformInsight] = Field(
        description="各平台洞察，按平台分开"
    )
    core_messaging: list[str] = Field(
        description="核心传播信息/卖点，提取3-5个关键词或短语"
    )
    threat_level: ThreatLevel = Field(
        description="对我方品牌的威胁等级评估"
    )
    threat_reason: str = Field(description="威胁等级判断原因（1-2句话）")
    actionable_recommendations: list[str] = Field(
        description="给我方品牌的可执行建议，2-3条", max_length=3
    )
    watch_out: Optional[str] = Field(
        default=None,
        description="需要重点关注的新动向或预警信号"
    )
