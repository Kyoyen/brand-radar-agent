"""Fail-closed output contract for the Brand Radar weekly scenario.

The model drafts the editorial fields in :class:`_ModelGeneratedOutput`.
Scenario identity, source provenance, material bookkeeping, provider
information, and the canonical meeting summary are supplied or derived by the
local runtime and cannot be overridden by model output.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any, Iterable, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)


__all__ = [
    "BrandRadarValidationError",
    "BrandRadarValidationIssue",
    "BrandRadarWeeklyOutput",
    "build_weekly_meeting_summary",
    "get_brand_radar_result_contract",
    "get_brand_radar_schema_prompt",
    "parse_brand_radar_output",
    "validate_investigation_preflight",
    "validate_investigation_trace",
]


def _card_value(card: Any, field: str) -> Any:
    if isinstance(card, dict):
        return card.get(field)
    return getattr(card, field, None)


def _priority_titles(
    cards: Iterable[Any],
    priority: str,
    *,
    limit: int = 3,
) -> str:
    titles: list[str] = []
    for card in cards:
        if _card_value(card, "priority") != priority:
            continue
        title = str(_card_value(card, "title") or "").strip()
        if priority == "needs_verification":
            title = re.sub(r"\s*(?:[（(]待核[）)]|待核)\s*$", "", title).strip()
        if title:
            titles.append(title)
    visible = titles[:limit]
    if len(titles) > limit:
        visible.append(f"另外 {len(titles) - limit} 项")
    return "、".join(visible)


def build_weekly_meeting_summary(cards: Iterable[Any]) -> str:
    """Build the canonical meeting opener from validated card priorities."""

    card_list = list(cards)
    sections = (
        ("follow_up_this_week", "本周优先讨论：", ""),
        (
            "needs_verification",
            "信息还不够，先别放进方案：",
            "；先找到能确认它的公开信息再决定。",
        ),
        ("actively_avoid", "明确不采用：", ""),
        ("continue_observing", "继续观察：", ""),
    )
    sentences: list[str] = []
    for priority, prefix, suffix in sections:
        titles = _priority_titles(card_list, priority)
        if titles:
            sentences.append(f"{prefix}{titles}{suffix}")
    return " ".join(sentences) or "本周暂无可用信号，请先补充观察材料。"


@dataclass(frozen=True, slots=True)
class BrandRadarValidationIssue:
    """One immutable, machine-readable issue safe to return to the model."""

    location: str
    message: str
    type: str

    def as_dict(self) -> dict[str, str]:
        return {
            "location": self.location,
            "message": self.message,
            "type": self.type,
        }


class BrandRadarValidationError(ValueError):
    """Raised when model output or injected runtime metadata is invalid."""

    def __init__(
        self,
        message: str,
        *,
        issues: Iterable[BrandRadarValidationIssue | dict[str, str]] = (),
    ) -> None:
        super().__init__(message)
        self._issues = tuple(
            (
                BrandRadarValidationIssue(
                    location=issue.location.strip() or "result",
                    message=issue.message,
                    type=issue.type,
                )
                if isinstance(issue, BrandRadarValidationIssue)
                else BrandRadarValidationIssue(
                    location=str(issue["location"]).strip() or "result",
                    message=str(issue["message"]),
                    type=str(issue["type"]),
                )
            )
            for issue in issues
        )

    @property
    def issues(self) -> tuple[BrandRadarValidationIssue, ...]:
        return self._issues


def _validation_issues(exc: ValidationError) -> tuple[BrandRadarValidationIssue, ...]:
    return tuple(
        BrandRadarValidationIssue(
            location=".".join(str(part) for part in error["loc"]) or "$",
            message=error["msg"],
            type=error["type"],
        )
        for error in exc.errors(include_input=False)
    )


def _iso_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("must be an ISO date in YYYY-MM-DD format") from exc
    return value


def _iso_datetime(value: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("must be an ISO-8601 date-time") from exc
    return value


NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
IsoDate = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(_iso_date),
]
IsoDateTime = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(_iso_datetime),
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _DateWindow(_StrictModel):
    start: IsoDate
    end: IsoDate

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if date.fromisoformat(self.start) > date.fromisoformat(self.end):
            raise ValueError("date window start cannot be later than end")
        return self


class _ObservationSettings(_StrictModel):
    """The fixed single-scenario settings produced by the Replay runtime."""

    brand: NonEmptyString | None = None
    category: NonEmptyString | None = None
    regions: list[NonEmptyString] = Field(default_factory=list)
    competitors: list[NonEmptyString] = Field(default_factory=list)
    keywords: list[NonEmptyString] = Field(default_factory=list)
    business_question: NonEmptyString | None = None
    observation_window: _DateWindow | None = None
    calendar_window: _DateWindow
    safety_boundaries: list[NonEmptyString] = Field(default_factory=list)
    review_deadline: IsoDate | None = None


class _SourceCatalogItem(_StrictModel):
    source_id: NonEmptyString
    title: NonEmptyString
    source_type: Literal["REPLAY", "PUBLIC", "MANUAL"]
    source_date: IsoDate
    url: NonEmptyString | None
    file: NonEmptyString
    verification_status: Literal["verified", "unverified"]


class _MaterialIssue(_StrictModel):
    source_id: NonEmptyString
    reason: NonEmptyString


class _MaterialLog(_StrictModel):
    read_success: list[NonEmptyString]
    read_failed: list[_MaterialIssue]
    excluded: list[_MaterialIssue]


class _VersionDecision(_StrictModel):
    source_id: NonEmptyString
    status: Literal[
        "current",
        "duplicate",
        "unverified",
        "failed",
        "expired",
        "superseded",
        "unresolved_conflict",
    ]
    effective_source_id: NonEmptyString
    reason: NonEmptyString


class _MergeRecord(_StrictModel):
    event_key: NonEmptyString
    source_ids: list[NonEmptyString] = Field(min_length=1)
    primary_source_id: NonEmptyString
    brands: list[NonEmptyString]
    regions: list[NonEmptyString]
    verification_status: Literal["verified", "unverified"]
    material_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_sources(self) -> Self:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError(f"merge record {self.event_key!r} has duplicate source_ids")
        if self.primary_source_id not in self.source_ids:
            raise ValueError(
                f"merge record {self.event_key!r} primary_source_id must be in source_ids"
            )
        if self.material_count != len(self.source_ids):
            raise ValueError(
                f"merge record {self.event_key!r} material_count must equal source_ids count"
            )
        return self


class _RunInfo(_StrictModel):
    mode: Literal["real", "mock"]
    provider: NonEmptyString
    model: NonEmptyString
    source_pack: NonEmptyString
    stages_completed: list[NonEmptyString]
    started_at: IsoDateTime
    completed_at: IsoDateTime


class _GoalSnapshot(_StrictModel):
    brand: NonEmptyString
    category: NonEmptyString
    regions: list[NonEmptyString] = Field(min_length=1)
    competitors: list[NonEmptyString] = Field(min_length=1)
    keywords: list[NonEmptyString] = Field(min_length=1)
    business_question: NonEmptyString


class _PlanStep(_StrictModel):
    step_id: NonEmptyString
    objective: NonEmptyString


class _SelectedAction(_StrictModel):
    action_id: NonEmptyString
    step_id: NonEmptyString
    action_type: Literal[
        "inspect_local_evidence",
        "compare_event_versions",
        "compare_competitor_evidence",
        "cross_check_conflicting_evidence",
    ]
    reason: NonEmptyString
    arguments: dict[str, JsonValue]
    source_ids: list[NonEmptyString]


class _ToolFeedback(_StrictModel):
    feedback_id: NonEmptyString
    action_id: NonEmptyString
    source_ids: list[NonEmptyString]
    summary: NonEmptyString
    outcome: NonEmptyString
    decision_hint: NonEmptyString


class _AdjustmentReason(_StrictModel):
    adjustment_id: NonEmptyString
    action_id: NonEmptyString
    feedback_id: NonEmptyString
    reason: NonEmptyString


class _AttemptIssue(_StrictModel):
    location: NonEmptyString
    message: NonEmptyString
    type: NonEmptyString


class _GenerationAttempt(_StrictModel):
    attempt: int = Field(ge=1, le=2)
    status: Literal["validation_failed", "validated"]
    issues: list[_AttemptIssue] = Field(default_factory=list)


class _InvestigationTrace(_StrictModel):
    goal_snapshot: _GoalSnapshot
    plan_steps: list[_PlanStep] = Field(min_length=1)
    selected_actions: list[_SelectedAction] = Field(min_length=1)
    tool_feedback: list[_ToolFeedback] = Field(min_length=1)
    adjustment_reasons: list[_AdjustmentReason] = Field(min_length=1)
    generation_attempts: list[_GenerationAttempt] = Field(max_length=2)


class _InvestigationPreflight(_StrictModel):
    """Program-owned trace fields that exist before model generation."""

    goal_snapshot: _GoalSnapshot
    plan_steps: list[_PlanStep] = Field(min_length=1)
    selected_actions: list[_SelectedAction] = Field(min_length=1)
    tool_feedback: list[_ToolFeedback] = Field(min_length=1)


class _IntelligenceCard(_StrictModel):
    card_id: NonEmptyString
    title: NonEmptyString
    fact_summary: NonEmptyString
    brands: list[NonEmptyString]
    event_date: IsoDate | None
    regions: list[NonEmptyString] = Field(min_length=1)
    event_type: NonEmptyString
    priority: Literal[
        "follow_up_this_week",
        "continue_observing",
        "actively_avoid",
        "needs_verification",
    ]
    why_it_matters: NonEmptyString
    recommendation: NonEmptyString
    risk_notes: list[NonEmptyString]
    pending_questions: list[NonEmptyString]
    source_ids: list[NonEmptyString] = Field(default_factory=list)
    feedback_ids: list[NonEmptyString] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pending_reason(self) -> Self:
        if self.priority == "needs_verification" and not self.pending_questions:
            raise ValueError(
                f"card {self.card_id!r} needs_verification but has no pending_questions"
            )
        if not self.source_ids and not self.feedback_ids:
            raise ValueError(
                f"card {self.card_id!r} must reference source_ids or feedback_ids"
            )
        if not self.source_ids and self.priority != "needs_verification":
            raise ValueError(
                f"card {self.card_id!r} has no source_ids and must be needs_verification"
            )
        return self


class _CalendarItem(_StrictModel):
    date: IsoDate
    title: NonEmptyString
    kind: NonEmptyString
    card_ids: list[NonEmptyString] = Field(min_length=1)


class _Keyword(_StrictModel):
    keyword: NonEmptyString
    why_it_matters: NonEmptyString
    card_ids: list[NonEmptyString] = Field(min_length=1)


class _Brief(_StrictModel):
    brief_id: NonEmptyString
    perspective: Literal[
        "consumption_scenario",
        "competitor_gap",
        "timing_window",
        "risk_control",
    ]
    angle: NonEmptyString
    why_now: NonEmptyString
    audience_or_scenario: NonEmptyString
    card_ids: list[NonEmptyString] = Field(min_length=1)
    next_step: NonEmptyString
    risk_note: NonEmptyString
    missing_evidence: list[NonEmptyString]

    @model_validator(mode="after")
    def research_steps_must_name_the_gap(self) -> Self:
        if not self.missing_evidence and any(
            marker in self.next_step for marker in ("调研", "核实", "收集证据", "补充证据")
        ):
            raise ValueError(
                f"brief {self.brief_id!r} asks for research but missing_evidence is empty"
            )
        return self


class _HumanReviewItem(_StrictModel):
    review_id: NonEmptyString
    question: NonEmptyString
    card_ids: list[NonEmptyString] = Field(min_length=1)


class _HumanReview(_StrictModel):
    status: Literal["awaiting_human_review"]
    items: list[_HumanReviewItem] = Field(min_length=1)
    external_actions: list[Any]

    @field_validator("external_actions")
    @classmethod
    def external_actions_must_be_empty(cls, value: list[Any]) -> list[Any]:
        if value:
            raise ValueError("external_actions must be empty before human review")
        return value


class _ModelGeneratedOutput(_StrictModel):
    """The only fields the language model is authorised to generate."""

    executive_summary: NonEmptyString
    intelligence_cards: list[_IntelligenceCard] = Field(min_length=1)
    calendar: list[_CalendarItem] = Field(min_length=1)
    keywords: list[_Keyword] = Field(min_length=1)
    briefs: list[_Brief]
    human_review: _HumanReview


class BrandRadarWeeklyOutput(_StrictModel):
    """Validated, provenance-preserving weekly result shared by CLI and UI."""

    schema_version: Literal["1.0", "1.1"]
    scenario_id: Literal["brand_radar_weekly"]
    observation_settings: _ObservationSettings
    source_catalog: list[_SourceCatalogItem] = Field(min_length=1)
    material_log: _MaterialLog
    version_decisions: list[_VersionDecision]
    merge_records: list[_MergeRecord]
    run_info: _RunInfo
    investigation_trace: _InvestigationTrace | None = None
    executive_summary: NonEmptyString
    intelligence_cards: list[_IntelligenceCard] = Field(min_length=1)
    calendar: list[_CalendarItem]
    keywords: list[_Keyword]
    briefs: list[_Brief]
    human_review: _HumanReview

    @model_validator(mode="after")
    def validate_evidence_graph(self) -> Self:
        unsupported_absence_phrases = (
            "无新动作",
            "没有新动作",
            "无营销动作",
            "没有营销动作",
        )
        generated_claims = [self.executive_summary]
        generated_claims.extend(card.fact_summary for card in self.intelligence_cards)
        generated_claims.extend(brief.why_now for brief in self.briefs)
        if any(
            phrase in claim
            for claim in generated_claims
            for phrase in unsupported_absence_phrases
        ):
            raise ValueError(
                "材料未覆盖不能写成品牌无动作；应写成当前观察包未提供相关动作材料"
            )

        if self.schema_version == "1.1":
            if self.investigation_trace is None:
                raise ValueError("schema_version 1.1 requires investigation_trace")
            _validate_generation_attempts(
                self.investigation_trace.generation_attempts,
                allow_empty=False,
            )
            expected_goal = {
                "brand": self.observation_settings.brand,
                "category": self.observation_settings.category,
                "regions": self.observation_settings.regions,
                "competitors": self.observation_settings.competitors,
                "keywords": self.observation_settings.keywords,
                "business_question": self.observation_settings.business_question,
            }
            if self.investigation_trace.goal_snapshot.model_dump() != expected_goal:
                raise ValueError(
                    "investigation_trace.goal_snapshot must match observation_settings"
                )
        elif self.investigation_trace is not None:
            raise ValueError("schema_version 1.0 cannot contain investigation_trace")

        source_ids = [source.source_id for source in self.source_catalog]
        self._require_unique("source_id", source_ids)
        known_sources = set(source_ids)

        for source_id in self.material_log.read_success:
            self._require_known("material_log.read_success source", source_id, known_sources)
        for issue in (*self.material_log.read_failed, *self.material_log.excluded):
            self._require_known("material_log source", issue.source_id, known_sources)

        for decision in self.version_decisions:
            self._require_known("version decision source", decision.source_id, known_sources)
            self._require_known(
                "version decision effective source",
                decision.effective_source_id,
                known_sources,
            )
        for record in self.merge_records:
            for source_id in record.source_ids:
                self._require_known("merge record source", source_id, known_sources)

        card_ids = [card.card_id for card in self.intelligence_cards]
        self._require_unique("card_id", card_ids)
        known_cards = set(card_ids)
        card_by_id = {card.card_id: card for card in self.intelligence_cards}
        feedback_by_id = (
            {
                item.feedback_id: item
                for item in self.investigation_trace.tool_feedback
            }
            if self.investigation_trace is not None
            else {}
        )
        action_by_id = (
            {
                item.action_id: item
                for item in self.investigation_trace.selected_actions
            }
            if self.investigation_trace is not None
            else {}
        )
        excluded_sources = {item.source_id for item in self.material_log.excluded}
        source_by_id = {source.source_id: source for source in self.source_catalog}
        conflicted_sources = {
            decision.source_id
            for decision in self.version_decisions
            if decision.status == "unresolved_conflict"
        }

        for card in self.intelligence_cards:
            for source_id in card.source_ids:
                self._require_known(f"card {card.card_id!r} source", source_id, known_sources)
                if source_id in excluded_sources:
                    raise ValueError(
                        f"card {card.card_id!r} references excluded source {source_id!r}"
                    )
            references_unverified = any(
                source_by_id[source_id].verification_status == "unverified"
                for source_id in card.source_ids
            )
            if references_unverified and card.priority != "needs_verification":
                raise ValueError(
                    f"card {card.card_id!r} references an unverified source and must be needs_verification"
                )
            if conflicted_sources.intersection(card.source_ids) and card.priority != "needs_verification":
                raise ValueError(
                    f"card {card.card_id!r} references an unresolved conflict and must be needs_verification"
                )
            for feedback_id in card.feedback_ids:
                if feedback_id not in feedback_by_id:
                    raise ValueError(
                        f"card {card.card_id!r} references unknown feedback {feedback_id!r}"
                    )
            if not card.source_ids:
                gap_feedback = [
                    feedback_by_id[feedback_id]
                    for feedback_id in card.feedback_ids
                    if feedback_by_id[feedback_id].outcome
                    in {"no_pack_evidence", "no_current_pack_evidence"}
                ]
                if not gap_feedback:
                    raise ValueError(
                        f"card {card.card_id!r} has no source_ids and must reference current evidence-gap feedback"
                    )

        for record in self.merge_records:
            event_sources = set(record.source_ids)
            if not any(
                event_sources.issubset(set(card.source_ids))
                for card in self.intelligence_cards
            ):
                raise ValueError(
                    f"merged event {record.event_key!r} must be represented by one card "
                    "that preserves all merged source_ids"
                )

        brief_ids = [brief.brief_id for brief in self.briefs]
        self._require_unique("brief_id", brief_ids)
        if len(self.briefs) != 3:
            raise ValueError("weekly output must contain exactly 3 briefs")
        perspectives = [brief.perspective for brief in self.briefs]
        if len(perspectives) != len(set(perspectives)):
            raise ValueError("the 3 briefs must use distinct perspectives")
        calendar_start = date.fromisoformat(self.observation_settings.calendar_window.start)
        calendar_end = date.fromisoformat(self.observation_settings.calendar_window.end)
        for item in self.calendar:
            item_date = date.fromisoformat(item.date)
            if not calendar_start <= item_date <= calendar_end:
                raise ValueError(
                    f"calendar item {item.title!r} date is outside calendar_window"
                )
            self._require_card_refs("calendar item", item.card_ids, known_cards)

        for keyword in self.keywords:
            self._require_card_refs(
                f"keyword {keyword.keyword!r}", keyword.card_ids, known_cards
            )
        for brief in self.briefs:
            self._require_card_refs(
                f"brief {brief.brief_id!r}", brief.card_ids, known_cards
            )
            self._require_competitor_card_support(
                f"brief {brief.brief_id!r}",
                [
                    brief.angle,
                    brief.why_now,
                    brief.audience_or_scenario,
                    brief.next_step,
                    brief.risk_note,
                ],
                brief.card_ids,
                card_by_id,
                feedback_by_id,
                action_by_id,
            )
        for review_item in self.human_review.items:
            self._require_card_refs(
                f"review item {review_item.review_id!r}",
                review_item.card_ids,
                known_cards,
            )
            self._require_competitor_card_support(
                f"review item {review_item.review_id!r}",
                [review_item.question],
                review_item.card_ids,
                card_by_id,
                feedback_by_id,
                action_by_id,
            )
        return self

    @staticmethod
    def _require_unique(label: str, values: list[str]) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        if duplicates:
            raise ValueError(f"duplicate {label}: {', '.join(sorted(duplicates))}")

    @staticmethod
    def _require_known(label: str, value: str, known: set[str]) -> None:
        if value not in known:
            raise ValueError(f"{label} references unknown id {value!r}")

    @classmethod
    def _require_card_refs(
        cls,
        label: str,
        references: list[str],
        known_cards: set[str],
    ) -> None:
        for card_id in references:
            cls._require_known(label, card_id, known_cards)

    def _require_competitor_card_support(
        self,
        label: str,
        texts: list[str],
        card_ids: list[str],
        card_by_id: dict[str, _IntelligenceCard],
        feedback_by_id: dict[str, _ToolFeedback],
        action_by_id: dict[str, _SelectedAction],
    ) -> None:
        mentioned = [
            competitor
            for competitor in self.observation_settings.competitors
            if any(competitor in text for text in texts)
        ]
        if not mentioned:
            return
        cards = [card_by_id[card_id] for card_id in card_ids]
        for competitor in mentioned:
            if not any(
                self._card_supports_competitor(
                    card,
                    competitor,
                    feedback_by_id,
                    action_by_id,
                )
                for card in cards
            ):
                raise ValueError(
                    f"{label} mentions competitor {competitor!r} but referenced cards do not support it"
                )

    @staticmethod
    def _card_supports_competitor(
        card: _IntelligenceCard,
        competitor: str,
        feedback_by_id: dict[str, _ToolFeedback],
        action_by_id: dict[str, _SelectedAction],
    ) -> bool:
        card_text = " ".join(
            [
                card.title,
                card.fact_summary,
                card.why_it_matters,
                card.recommendation,
                *card.risk_notes,
                *card.pending_questions,
            ]
        )
        if competitor in card.brands or competitor in card_text:
            return True
        for feedback_id in card.feedback_ids:
            feedback = feedback_by_id.get(feedback_id)
            if feedback is None:
                continue
            action = action_by_id.get(feedback.action_id)
            if (
                action is not None
                and action.action_type == "compare_competitor_evidence"
                and action.arguments.get("competitor") == competitor
                and feedback.outcome
                in {"no_pack_evidence", "no_current_pack_evidence"}
            ):
                return True
        return False


_FENCED_JSON = re.compile(
    r"\A```(?:json)?[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```[ \t]*\Z",
    flags=re.IGNORECASE,
)


def _decode_model_json(raw: str) -> Any:
    if not isinstance(raw, str) or not raw.strip():
        message = "模型结果为空，必须返回 JSON 对象"
        raise BrandRadarValidationError(
            message,
            issues=[
                BrandRadarValidationIssue(
                    location="result",
                    message=message,
                    type="json_missing",
                )
            ],
        )
    candidate = raw.strip()
    fenced = _FENCED_JSON.fullmatch(candidate)
    if fenced:
        candidate = fenced.group("body").strip()
    elif candidate.startswith("```"):
        message = "JSON 代码围栏格式无效"
        raise BrandRadarValidationError(
            message,
            issues=[
                BrandRadarValidationIssue(
                    location="result",
                    message=message,
                    type="json_fence_invalid",
                )
            ],
        )
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        message = f"模型结果不是有效 JSON（line {exc.lineno}, column {exc.colno}）"
        raise BrandRadarValidationError(
            message,
            issues=[
                BrandRadarValidationIssue(
                    location="result",
                    message=message,
                    type="json_invalid",
                )
            ],
        ) from exc


def get_brand_radar_result_contract() -> str:
    """Return rules and schema for the six-field editorial ``result`` object."""
    schema = json.dumps(
        _ModelGeneratedOutput.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )
    return f"""
【result 字段业务规则】
1. 每张卡的 source_ids 只能引用本次提供、未被排除的来源；未核验来源只能形成 needs_verification 卡片。
2. needs_verification 卡片必须写明至少一个 pending_questions。每张卡通常必须引用 source_ids；唯一允许 source_ids 为空的情况，是本次 Agent 确实执行了该竞品调查并收到 no_pack_evidence 或 no_current_pack_evidence，此时缺证卡必须引用对应 feedback_ids。没有执行该竞品调查时，不得仅凭来源目录里没出现它就自行创建缺证卡；已有当前材料的竞品卡必须引用实际 source_ids，过期或被替换的材料不能作为当前事实来源。
3. 输入中的每一条 merge_records 都必须形成一张 intelligence_card；该卡的 source_ids 必须完整保留该 merge record 的全部 source_ids。低优先级背景也不能省略，只能用 priority 区分处理方式。
4. calendar、keywords、briefs 和 human_review.items 的 card_ids 只能引用实际输出的卡片。
5. Brief 或 human_review 问题如果点名某个竞品，引用的卡片必须真实包含该竞品，或引用该竞品 evidence-gap 反馈形成缺证卡；不得把缺证竞品挂到无关瑞幸卡，也不得点名本次没有材料且没有实际调查反馈的竞品。
6. 材料没有覆盖某品牌的新动作时，只能写“当前观察包未提供相关动作材料”，不得写成“品牌无新动作”或“品牌没有营销动作”。Brief 的 next_step 如果要求调研、核实或收集证据，missing_evidence 必须列出具体缺口。
7. executive_summary 用自然语言概括 Agent 的业务判断；其中的事实仍必须可以回到情报卡和来源。HTML 周会稿会再按卡片 priority 组织成稳定的首屏结论。
8. 恰好输出 3 条 Brief，brief_id 各异且 perspective 各异。
9. human_review.status 必须为 awaiting_human_review，external_actions 必须是空数组；不得发送、发布、投放或改预算。

【result 字段 JSON Schema】
{schema}
""".strip()


def get_brand_radar_schema_prompt() -> str:
    """Return the standalone model-result contract used by legacy callers."""

    return f"""
【Brand Radar weekly 最终输出】
只输出一个 JSON 对象（可使用 ```json 代码围栏），不要附解释文字。
顶层只能包含 executive_summary、intelligence_cards、calendar、keywords、briefs、human_review。
不要输出 schema_version、scenario_id、observation_settings、source_catalog、material_log、
version_decisions、merge_records、run_info、investigation_trace、provider、model 或 mode；
这些字段只由程序注入。

{get_brand_radar_result_contract()}
""".strip()


def _validate_investigation_graph(
    validated: _InvestigationPreflight | _InvestigationTrace,
    *,
    known_source_ids: set[str],
    adjustments: list[_AdjustmentReason] | None = None,
) -> None:
    steps = {step.step_id: step for step in validated.plan_steps}
    actions = {action.action_id: action for action in validated.selected_actions}
    feedback = {item.feedback_id: item for item in validated.tool_feedback}

    all_ids = [step.step_id for step in validated.plan_steps]
    all_ids.extend(action.action_id for action in validated.selected_actions)
    all_ids.extend(item.feedback_id for item in validated.tool_feedback)
    if adjustments is not None:
        all_ids.extend(item.adjustment_id for item in adjustments)
    duplicate_ids = sorted(
        identifier
        for identifier, count in Counter(all_ids).items()
        if count > 1
    )
    if duplicate_ids:
        raise ValueError(
            f"investigation trace has duplicate ids: {', '.join(duplicate_ids)}"
        )

    actions_per_step = Counter(action.step_id for action in validated.selected_actions)
    for action in validated.selected_actions:
        if action.step_id not in steps:
            raise ValueError(
                f"action {action.action_id!r} references unknown step {action.step_id!r}"
            )
        if action.action_type == "compare_competitor_evidence":
            competitor = action.arguments.get("competitor")
            if isinstance(competitor, str):
                overclaimed = sorted(
                    item
                    for item in validated.goal_snapshot.competitors
                    if item != competitor and item in action.reason
                )
                if overclaimed:
                    raise ValueError(
                        f"action {action.action_id!r} checks {competitor!r} but reason "
                        "claims other competitors: "
                        f"{', '.join(overclaimed)}"
                    )
        _validate_trace_sources(
            f"action {action.action_id!r}", action.source_ids, known_source_ids
        )
    unused_steps = sorted(step_id for step_id in steps if not actions_per_step[step_id])
    if unused_steps:
        raise ValueError(
            f"plan steps have no selected action: {', '.join(unused_steps)}"
        )

    feedback_per_action = Counter(item.action_id for item in validated.tool_feedback)
    for item in validated.tool_feedback:
        action = actions.get(item.action_id)
        if action is None:
            raise ValueError(
                f"feedback {item.feedback_id!r} references unknown action {item.action_id!r}"
            )
        _validate_trace_sources(
            f"feedback {item.feedback_id!r}", item.source_ids, known_source_ids
        )
        unexpected_sources = sorted(set(item.source_ids) - set(action.source_ids))
        if unexpected_sources:
            raise ValueError(
                f"feedback {item.feedback_id!r} references sources outside action "
                f"{item.action_id!r}: {', '.join(unexpected_sources)}"
            )

    for action_id in actions:
        if feedback_per_action[action_id] != 1:
            raise ValueError(
                f"action {action_id!r} must have exactly one tool feedback"
            )

    if adjustments is None:
        return
    adjustments_per_action = Counter(item.action_id for item in adjustments)
    adjustments_per_feedback = Counter(item.feedback_id for item in adjustments)
    for adjustment in adjustments:
        action = actions.get(adjustment.action_id)
        item = feedback.get(adjustment.feedback_id)
        if action is None:
            raise ValueError(
                f"adjustment {adjustment.adjustment_id!r} references unknown action "
                f"{adjustment.action_id!r}"
            )
        if item is None:
            raise ValueError(
                f"adjustment {adjustment.adjustment_id!r} references unknown feedback "
                f"{adjustment.feedback_id!r}"
            )
        if item.action_id != action.action_id:
            raise ValueError(
                f"adjustment {adjustment.adjustment_id!r} action and feedback do not match"
            )
    for action_id in actions:
        if adjustments_per_action[action_id] != 1:
            raise ValueError(
                f"action {action_id!r} must have exactly one adjustment reason"
            )
    for feedback_id in feedback:
        if adjustments_per_feedback[feedback_id] != 1:
            raise ValueError(
                f"feedback {feedback_id!r} must have exactly one adjustment reason"
            )


def _investigation_validation_error(exc: Exception) -> BrandRadarValidationError:
    if isinstance(exc, ValidationError):
        issues = _validation_issues(exc)
    else:
        issues = [
            BrandRadarValidationIssue(
                location="investigation_trace",
                message=str(exc),
                type="value_error",
            )
        ]
    return BrandRadarValidationError(
        f"Brand Radar 调查轨迹校验失败：{exc}",
        issues=issues,
    )


def validate_investigation_preflight(
    trace: dict,
    *,
    known_source_ids: set[str],
) -> _InvestigationPreflight:
    """Validate only program-owned goal, plan, actions, and feedback."""

    try:
        validated = _InvestigationPreflight.model_validate(trace)
        _validate_investigation_graph(
            validated,
            known_source_ids=known_source_ids,
        )
        return validated
    except BrandRadarValidationError:
        raise
    except (ValidationError, TypeError, ValueError) as exc:
        raise _investigation_validation_error(exc) from exc


def validate_investigation_trace(
    trace: dict,
    *,
    known_source_ids: set[str],
) -> _InvestigationTrace:
    """Validate the complete trace after model generation."""

    try:
        validated = _InvestigationTrace.model_validate(trace)
        _validate_investigation_graph(
            validated,
            known_source_ids=known_source_ids,
            adjustments=validated.adjustment_reasons,
        )
        _validate_generation_attempts(
            validated.generation_attempts,
            allow_empty=True,
        )
        return validated
    except BrandRadarValidationError:
        raise
    except (ValidationError, TypeError, ValueError) as exc:
        raise _investigation_validation_error(exc) from exc


def _validate_trace_sources(
    label: str,
    source_ids: list[str],
    known_source_ids: set[str],
) -> None:
    duplicates = sorted(
        source_id
        for source_id, count in Counter(source_ids).items()
        if count > 1
    )
    if duplicates:
        raise ValueError(f"{label} has duplicate source ids: {', '.join(duplicates)}")
    unknown = sorted(set(source_ids) - known_source_ids)
    if unknown:
        raise ValueError(f"{label} references unknown sources: {', '.join(unknown)}")


def _validate_generation_attempts(
    attempts: list[_GenerationAttempt],
    *,
    allow_empty: bool,
) -> None:
    if not attempts:
        if allow_empty:
            return
        raise ValueError("final investigation trace requires one validated attempt")

    for attempt in attempts:
        if attempt.status == "validation_failed" and not attempt.issues:
            raise ValueError(
                f"generation attempt {attempt.attempt} failed validation without issues"
            )
        if attempt.status == "validated" and attempt.issues:
            raise ValueError(
                f"generation attempt {attempt.attempt} validated but still contains issues"
            )

    sequence = tuple((item.attempt, item.status) for item in attempts)
    allowed = {
        ((1, "validated"),),
        ((1, "validation_failed"), (2, "validated")),
    }
    if sequence not in allowed:
        raise ValueError(
            "generation attempts must be [1 validated] or "
            "[1 validation_failed, 2 validated]"
        )


def parse_brand_radar_output(
    raw: str,
    *,
    observation_settings: dict,
    source_catalog: list[dict],
    material_log: dict,
    version_decisions: list[dict],
    merge_records: list[dict],
    run_info: dict,
    investigation_trace: dict | None = None,
) -> BrandRadarWeeklyOutput:
    """Parse model JSON, inject trusted metadata, and validate the full graph.

    Any parse, shape, provenance, or cross-reference failure is converted to
    :class:`BrandRadarValidationError`; this function never returns raw text.
    """

    try:
        decoded = _decode_model_json(raw)
        generated = _ModelGeneratedOutput.model_validate(decoded)
        validated_trace = None
        if investigation_trace is not None:
            validated_trace = validate_investigation_trace(
                investigation_trace,
                known_source_ids={
                    item["source_id"]
                    for item in source_catalog
                    if isinstance(item, dict) and isinstance(item.get("source_id"), str)
                },
            )
        validated = BrandRadarWeeklyOutput.model_validate(
            {
                "schema_version": "1.1" if investigation_trace is not None else "1.0",
                "scenario_id": "brand_radar_weekly",
                "observation_settings": observation_settings,
                "source_catalog": source_catalog,
                "material_log": material_log,
                "version_decisions": version_decisions,
                "merge_records": merge_records,
                "run_info": run_info,
                "investigation_trace": (
                    validated_trace.model_dump(mode="python")
                    if validated_trace is not None
                    else None
                ),
                **generated.model_dump(mode="python"),
            }
        )
        summary = build_weekly_meeting_summary(validated.intelligence_cards)
        if validated.run_info.mode == "mock":
            summary = (
                "[MOCK 输出｜仅供程序烟雾测试，不能作为业务验收] "
                + summary
            )
        return validated.model_copy(update={"executive_summary": summary})
    except BrandRadarValidationError:
        raise
    except ValidationError as exc:
        issues = _validation_issues(exc)
        details = json.dumps(
            [issue.as_dict() for issue in issues],
            ensure_ascii=False,
        )
        raise BrandRadarValidationError(
            f"Brand Radar 结果校验失败：{details}",
            issues=issues,
        ) from exc
    except (TypeError, ValueError) as exc:
        issue = BrandRadarValidationIssue(
            location="result",
            message=str(exc),
            type="value_error",
        )
        raise BrandRadarValidationError(
            f"Brand Radar 结果校验失败：{exc}",
            issues=[issue],
        ) from exc
