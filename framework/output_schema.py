"""
Output Schema — Agent 统一输出范式
=====================================
辅助策略判断和创意决策的输出，必须满足三个要求：
  1. 可比较：相同场景多次执行能横向对比
  2. 可追溯：每个建议都能回溯到具体数据依据
  3. 可决策：明确告诉用户「现在该做什么」，而不是甩一堆数据让用户自己想

四段式结构（适用于所有场景）：
  观察 (Observation)  — 看到了什么客观事实
  洞察 (Insight)      — 这些事实意味着什么
  决策点 (Decision)   — 用户面临哪些选择
  建议 (Action)       — 推荐怎么做，含置信度

每条洞察、决策、建议都必须有 evidence_refs 指向具体的观察项。
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── 基础枚举 ──────────────────────────────────────────────────────────

class Confidence(str, Enum):
    """置信度——明确告诉用户这条建议有多可靠"""
    HIGH   = "high"    # 数据充分，结论明确
    MEDIUM = "medium"  # 数据可信，但有不确定因素
    LOW    = "low"     # 数据有限或冲突，仅供参考


class Priority(str, Enum):
    """优先级——帮用户决定先做什么"""
    P0 = "p0"  # 立即行动
    P1 = "p1"  # 本周内
    P2 = "p2"  # 计划安排
    P3 = "p3"  # 备选


class Effort(str, Enum):
    """投入估算——配合优先级判断 ROI"""
    LOW    = "low"     # 1人/0.5天内
    MEDIUM = "medium"  # 1-2人/1-3天
    HIGH   = "high"    # 多人/1周以上


# ── 四段式结构 ────────────────────────────────────────────────────────

class Observation(BaseModel):
    """一条客观观察——必须可被验证"""
    id: str = Field(description="编号 O1, O2 ...，供后续 evidence_refs 引用")
    fact: str = Field(description="一句话陈述事实，不带判断")
    metric: Optional[str] = Field(default=None, description="量化数据，如 '互动量 12.5万'")
    source: str = Field(description="数据来源，如 'xiaohongshu_api', 'mock', 'pytrends'")


class Insight(BaseModel):
    """一条洞察——基于观察的判断"""
    id: str = Field(description="编号 I1, I2 ...")
    statement: str = Field(description="一句话洞察，说明 fact 意味着什么")
    evidence_refs: list[str] = Field(description="引用的 Observation id 列表，如 ['O1','O3']")
    so_what: str = Field(description="对营销策略意味着什么，避免空话")


class DecisionPoint(BaseModel):
    """决策点——明确用户面临的选择"""
    id: str = Field(description="编号 D1, D2 ...")
    question: str = Field(description="决策问题，如 '是否跟进竞品的露营场景内容？'")
    options: list[str] = Field(description="可选项，至少 2 个")
    evidence_refs: list[str] = Field(description="支撑该决策点的 Observation/Insight id")


class Action(BaseModel):
    """推荐行动——必须具体可执行"""
    id: str = Field(description="编号 A1, A2 ...")
    what: str = Field(description="做什么，动词开头，具体到可分配")
    why: str = Field(description="一句话说明为什么")
    priority: Priority
    effort: Effort
    confidence: Confidence
    owner_hint: Optional[str] = Field(default=None, description="建议负责人角色，如 '内容组', '品牌经理'")
    evidence_refs: list[str] = Field(description="引用的 Observation/Insight id")


class AgentOutput(BaseModel):
    """Agent 最终输出——所有场景统一格式"""
    scenario_id: str = Field(description="场景 ID")
    task_description: str = Field(description="用户原始任务描述")
    executive_summary: str = Field(description="2-3 句执行摘要，直接给老板看的版本")

    observations: list[Observation] = Field(description="客观观察，至少 3 条")
    insights: list[Insight]         = Field(description="洞察，至少 1 条")
    decision_points: list[DecisionPoint] = Field(default_factory=list, description="决策点，可为空")
    actions: list[Action]           = Field(description="推荐行动，至少 1 条")

    open_questions: list[str] = Field(default_factory=list,
                                       description="未能解答的问题，需人工跟进")
    next_check: Optional[str] = Field(default=None,
                                       description="建议下次复查时间，如 '7天后'")

    def to_markdown(self) -> str:
        """格式化为 Markdown，用于飞书/邮件推送"""
        lines = [
            f"# {self.scenario_id} 报告\n",
            f"**任务**：{self.task_description}\n",
            f"## 执行摘要\n{self.executive_summary}\n",
            "## 观察\n",
        ]
        for o in self.observations:
            metric = f" `{o.metric}`" if o.metric else ""
            lines.append(f"- **{o.id}**{metric} {o.fact}  _[来源:{o.source}]_")

        lines.append("\n## 洞察\n")
        for i in self.insights:
            refs = ", ".join(i.evidence_refs)
            lines.append(f"- **{i.id}** {i.statement}  _[依据:{refs}]_")
            lines.append(f"  - 意味着：{i.so_what}")

        if self.decision_points:
            lines.append("\n## 决策点\n")
            for d in self.decision_points:
                lines.append(f"- **{d.id}** {d.question}")
                for opt in d.options:
                    lines.append(f"  - [ ] {opt}")

        lines.append("\n## 推荐行动\n")
        for a in self.actions:
            badges = f"`{a.priority.value.upper()}` `投入:{a.effort.value}` `置信:{a.confidence.value}`"
            owner = f" → {a.owner_hint}" if a.owner_hint else ""
            lines.append(f"- **{a.id}** {a.what}{owner}  {badges}")
            lines.append(f"  - 理由：{a.why}")

        if self.open_questions:
            lines.append("\n## 待解答\n")
            for q in self.open_questions:
                lines.append(f"- {q}")

        if self.next_check:
            lines.append(f"\n_下次复查：{self.next_check}_")

        return "\n".join(lines)


# ── 范例：让 LLM 看到结构 ─────────────────────────────────────────────

EXAMPLE_OUTPUT = AgentOutput(
    scenario_id="competitive_analysis",
    task_description="分析麦当劳今天在小红书的动态",
    executive_summary="麦当劳本周在小红书发布 12 篇内容，互动同比 +35%，主推「夏日轻食」概念抢占健康场景，对我们形成中等威胁。建议本周内推出对标内容。",
    observations=[
        Observation(id="O1", fact="麦当劳近7天发布 12 篇笔记", metric="频率: 1.7篇/天",
                    source="xiaohongshu_api"),
        Observation(id="O2", fact="主话题为 #夏日轻食", metric="占比 67%",
                    source="xiaohongshu_api"),
        Observation(id="O3", fact="平均互动量较上周提升", metric="+35%",
                    source="xiaohongshu_api"),
    ],
    insights=[
        Insight(id="I1", statement="麦当劳正在用「轻食」标签重塑健康形象",
                evidence_refs=["O2", "O3"],
                so_what="若不回应，我们「速食=不健康」的标签会被强化，影响白领客群"),
    ],
    decision_points=[
        DecisionPoint(id="D1", question="是否跟进轻食内容方向？",
                      options=["快速跟进，本周出 3 篇对标", "差异化定位，主打另一场景", "暂不动作，观察 2 周"],
                      evidence_refs=["I1"]),
    ],
    actions=[
        Action(id="A1", what="本周内发布 3 篇主打健康场景的图文",
               why="抢占同标签流量，避免被定型",
               priority=Priority.P0, effort=Effort.MEDIUM, confidence=Confidence.HIGH,
               owner_hint="内容组", evidence_refs=["I1", "O2"]),
    ],
    open_questions=["麦当劳是否同步在抖音投放？需补充检查"],
    next_check="7天后",
)


def get_schema_prompt() -> str:
    """注入到 system_prompt 的输出格式说明"""
    return """
【输出要求】最终回答必须是符合以下结构的 JSON，可被 AgentOutput Pydantic 模型解析：

{
  "scenario_id": "...",
  "task_description": "...",
  "executive_summary": "2-3句话，老板看的版本",
  "observations": [{"id": "O1", "fact": "...", "metric": "...", "source": "..."}],
  "insights": [{"id": "I1", "statement": "...", "evidence_refs": ["O1"], "so_what": "..."}],
  "decision_points": [{"id": "D1", "question": "...", "options": ["A","B"], "evidence_refs": ["I1"]}],
  "actions": [{"id": "A1", "what": "...", "why": "...", "priority": "p0|p1|p2|p3",
               "effort": "low|medium|high", "confidence": "high|medium|low",
               "owner_hint": "...", "evidence_refs": ["I1"]}],
  "open_questions": ["..."],
  "next_check": "7天后"
}

要求：
1. 每个 insight/decision/action 必须通过 evidence_refs 引用 observation 或 insight 的 id
2. observations 至少 3 条，actions 至少 1 条
3. executive_summary 直接讲结论，不要描述工具调用过程
4. 不能编造数据；如果工具返回的是 mock，在 source 中标注 "mock"
"""
