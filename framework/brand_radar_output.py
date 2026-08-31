"""Fail-closed output contract for the Brand Radar weekly scenario.

Only the six editorial fields in :class:`_ModelGeneratedOutput` may come from
the model.  Scenario identity, source provenance, material bookkeeping, and
provider information are supplied by the local runtime and cannot be
overridden by model output.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)


__all__ = [
    "BrandRadarValidationError",
    "BrandRadarWeeklyOutput",
    "get_brand_radar_schema_prompt",
    "parse_brand_radar_output",
]


class BrandRadarValidationError(ValueError):
    """Raised when model output or injected runtime metadata is invalid."""


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
    source_ids: list[NonEmptyString] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_pending_reason(self) -> Self:
        if self.priority == "needs_verification" and not self.pending_questions:
            raise ValueError(
                f"card {self.card_id!r} needs_verification but has no pending_questions"
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

    schema_version: Literal["1.0"]
    scenario_id: Literal["brand_radar_weekly"]
    observation_settings: _ObservationSettings
    source_catalog: list[_SourceCatalogItem] = Field(min_length=1)
    material_log: _MaterialLog
    version_decisions: list[_VersionDecision]
    merge_records: list[_MergeRecord]
    run_info: _RunInfo
    executive_summary: NonEmptyString
    intelligence_cards: list[_IntelligenceCard] = Field(min_length=1)
    calendar: list[_CalendarItem]
    keywords: list[_Keyword]
    briefs: list[_Brief]
    human_review: _HumanReview

    @model_validator(mode="after")
    def validate_evidence_graph(self) -> Self:
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
        excluded_sources = {item.source_id for item in self.material_log.excluded}
        source_by_id = {source.source_id: source for source in self.source_catalog}

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
        for review_item in self.human_review.items:
            self._require_card_refs(
                f"review item {review_item.review_id!r}",
                review_item.card_ids,
                known_cards,
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


_FENCED_JSON = re.compile(
    r"\A```(?:json)?[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```[ \t]*\Z",
    flags=re.IGNORECASE,
)


def _decode_model_json(raw: str) -> Any:
    if not isinstance(raw, str) or not raw.strip():
        raise BrandRadarValidationError("模型结果为空，必须返回 JSON 对象")
    candidate = raw.strip()
    fenced = _FENCED_JSON.fullmatch(candidate)
    if fenced:
        candidate = fenced.group("body").strip()
    elif candidate.startswith("```"):
        raise BrandRadarValidationError("JSON 代码围栏格式无效")
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise BrandRadarValidationError(
            f"模型结果不是有效 JSON（line {exc.lineno}, column {exc.colno}）"
        ) from exc


def get_brand_radar_schema_prompt() -> str:
    """Return the model-only JSON contract and non-negotiable safety rules."""

    schema = json.dumps(
        _ModelGeneratedOutput.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )
    return f"""
【Brand Radar weekly 最终输出】
只输出一个 JSON 对象（可使用 ```json 代码围栏），不要附解释文字。
顶层只能包含 executive_summary、intelligence_cards、calendar、keywords、briefs、human_review。
不要输出 schema_version、scenario_id、observation_settings、source_catalog、material_log、
version_decisions、merge_records、run_info、provider、model 或 mode；这些字段只由程序注入。

硬性规则：
1. 每张卡的 source_ids 只能引用本次提供、未被排除的来源；未核验来源只能形成 needs_verification 卡片。
2. needs_verification 卡片必须写明至少一个 pending_questions。
3. 输入中的每一条 merge_records 都必须形成一张 intelligence_card；该卡的 source_ids 必须完整保留该 merge record 的全部 source_ids。低优先级背景也不能省略，只能用 priority 区分处理方式。
4. calendar、keywords、briefs 和 human_review.items 的 card_ids 只能引用实际输出的卡片。
5. 恰好输出 3 条 Brief，brief_id 各异且 perspective 各异。
6. human_review.status 必须为 awaiting_human_review，external_actions 必须是空数组；不得发送、发布、投放或改预算。

JSON Schema：
{schema}
""".strip()


def parse_brand_radar_output(
    raw: str,
    *,
    observation_settings: dict,
    source_catalog: list[dict],
    material_log: dict,
    version_decisions: list[dict],
    merge_records: list[dict],
    run_info: dict,
) -> BrandRadarWeeklyOutput:
    """Parse model JSON, inject trusted metadata, and validate the full graph.

    Any parse, shape, provenance, or cross-reference failure is converted to
    :class:`BrandRadarValidationError`; this function never returns raw text.
    """

    try:
        decoded = _decode_model_json(raw)
        generated = _ModelGeneratedOutput.model_validate(decoded)
        return BrandRadarWeeklyOutput.model_validate(
            {
                "schema_version": "1.0",
                "scenario_id": "brand_radar_weekly",
                "observation_settings": observation_settings,
                "source_catalog": source_catalog,
                "material_log": material_log,
                "version_decisions": version_decisions,
                "merge_records": merge_records,
                "run_info": run_info,
                **generated.model_dump(mode="python"),
            }
        )
    except BrandRadarValidationError:
        raise
    except ValidationError as exc:
        details = json.dumps(
            [
                {
                    "location": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
                for error in exc.errors(include_input=False)
            ],
            ensure_ascii=False,
        )
        raise BrandRadarValidationError(f"Brand Radar 结果校验失败：{details}") from exc
    except (TypeError, ValueError) as exc:
        raise BrandRadarValidationError(f"Brand Radar 结果校验失败：{exc}") from exc
