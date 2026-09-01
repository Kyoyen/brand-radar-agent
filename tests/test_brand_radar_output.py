from __future__ import annotations

import copy
import json
import unittest

from framework.brand_radar_output import (
    BrandRadarValidationError,
    BrandRadarWeeklyOutput,
    get_brand_radar_schema_prompt,
    parse_brand_radar_output,
)


class BrandRadarOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generated = {
            "executive_summary": "下周应跟进工作日早餐场景，同时把未经核验的竞品传闻留在待核区。",
            "intelligence_cards": [
                {
                    "card_id": "card-breakfast",
                    "title": "工作日早餐窗口",
                    "fact_summary": "公开活动日历显示下周存在早餐消费沟通窗口。",
                    "brands": ["瑞幸咖啡"],
                    "event_date": "2026-09-08",
                    "regions": ["全国"],
                    "event_type": "consumption_window",
                    "priority": "follow_up_this_week",
                    "why_it_matters": "时间窗与周企划执行期重合。",
                    "recommendation": "讨论早餐场景内容角度。",
                    "risk_notes": [],
                    "pending_questions": [],
                    "source_ids": ["source-verified"],
                },
                {
                    "card_id": "card-rumour",
                    "title": "竞品联名传闻待核",
                    "fact_summary": "人工摘录提到竞品可能推出联名，但尚无公开确认。",
                    "brands": ["库迪咖啡"],
                    "event_date": None,
                    "regions": ["上海"],
                    "event_type": "competitor_move",
                    "priority": "needs_verification",
                    "why_it_matters": "若属实可能影响同周内容排期。",
                    "recommendation": "核对竞品官方渠道后再判断。",
                    "risk_notes": ["不得把传闻写成已发布事实。"],
                    "pending_questions": ["竞品是否已经官宣？"],
                    "source_ids": ["source-unverified"],
                },
            ],
            "calendar": [
                {
                    "date": "2026-09-08",
                    "title": "早餐场景讨论窗口",
                    "kind": "consumption_moment",
                    "card_ids": ["card-breakfast"],
                }
            ],
            "keywords": [
                {
                    "keyword": "早餐",
                    "why_it_matters": "与本周可执行消费场景直接相关。",
                    "card_ids": ["card-breakfast"],
                }
            ],
            "briefs": [
                {
                    "brief_id": "brief-scenario",
                    "perspective": "consumption_scenario",
                    "angle": "把早餐从折扣表达转为通勤补给场景。",
                    "why_now": "下周工作日窗口明确。",
                    "audience_or_scenario": "通勤人群",
                    "card_ids": ["card-breakfast"],
                    "next_step": "由企划人员评估门店与内容资源。",
                    "risk_note": "避免无依据的销量承诺。",
                    "missing_evidence": [],
                },
                {
                    "brief_id": "brief-gap",
                    "perspective": "competitor_gap",
                    "angle": "在竞品消息未确认前保留差异化表达空间。",
                    "why_now": "竞品传闻尚处待核。",
                    "audience_or_scenario": "上海年轻白领",
                    "card_ids": ["card-rumour"],
                    "next_step": "先核验竞品官方信息。",
                    "risk_note": "不得引用传闻作为确定事实。",
                    "missing_evidence": ["竞品官方公告"],
                },
                {
                    "brief_id": "brief-timing",
                    "perspective": "timing_window",
                    "angle": "在周中形成早餐主题的小范围内容测试草案。",
                    "why_now": "日历节点位于本周执行窗内。",
                    "audience_or_scenario": "周二至周四早高峰",
                    "card_ids": ["card-breakfast"],
                    "next_step": "提交人工复核，不自动发布。",
                    "risk_note": "需确认既有 Campaign 不冲突。",
                    "missing_evidence": ["本周既有排期"],
                },
            ],
            "human_review": {
                "status": "awaiting_human_review",
                "items": [
                    {
                        "review_id": "review-rumour",
                        "question": "是否已经取得竞品官方确认？",
                        "card_ids": ["card-rumour"],
                    }
                ],
                "external_actions": [],
            },
        }
        self.runtime = {
            "observation_settings": {
                "brand": "瑞幸咖啡",
                "category": "现制咖啡",
                "regions": ["全国", "上海"],
                "competitors": ["库迪咖啡"],
                "keywords": ["早餐"],
                "business_question": "下周有哪些值得跟进或待核的信号？",
                "observation_window": {"start": "2026-09-07", "end": "2026-09-13"},
                "calendar_window": {"start": "2026-09-04", "end": "2026-10-03"},
                "safety_boundaries": ["所有对外动作必须人工确认"],
                "review_deadline": "2026-09-04",
            },
            "source_catalog": [
                {
                    "source_id": "source-verified",
                    "title": "早餐消费节点",
                    "source_type": "PUBLIC",
                    "source_date": "2026-08-30",
                    "url": "https://example.com/breakfast",
                    "file": "sources/breakfast.md",
                    "verification_status": "verified",
                },
                {
                    "source_id": "source-unverified",
                    "title": "竞品联名人工摘录",
                    "source_type": "MANUAL",
                    "source_date": "2026-08-31",
                    "url": None,
                    "file": "sources/rumour.md",
                    "verification_status": "unverified",
                },
                {
                    "source_id": "source-expired",
                    "title": "已过期活动",
                    "source_type": "REPLAY",
                    "source_date": "2026-07-01",
                    "url": "https://example.com/expired",
                    "file": "sources/expired.md",
                    "verification_status": "verified",
                },
            ],
            "material_log": {
                "read_success": ["source-verified", "source-unverified", "source-expired"],
                "read_failed": [],
                "excluded": [{"source_id": "source-expired", "reason": "活动已过期"}],
            },
            "version_decisions": [
                {
                    "source_id": "source-verified",
                    "status": "current",
                    "effective_source_id": "source-verified",
                    "reason": "本周有效来源",
                },
                {
                    "source_id": "source-unverified",
                    "status": "unverified",
                    "effective_source_id": "source-unverified",
                    "reason": "仍待公开核验",
                },
                {
                    "source_id": "source-expired",
                    "status": "expired",
                    "effective_source_id": "source-expired",
                    "reason": "有效期早于观察窗",
                },
            ],
            "merge_records": [
                {
                    "event_key": "breakfast-window",
                    "source_ids": ["source-verified"],
                    "primary_source_id": "source-verified",
                    "brands": ["瑞幸咖啡"],
                    "regions": ["全国"],
                    "verification_status": "verified",
                    "material_count": 1,
                },
                {
                    "event_key": "competitor-rumour",
                    "source_ids": ["source-unverified"],
                    "primary_source_id": "source-unverified",
                    "brands": ["库迪咖啡"],
                    "regions": ["上海"],
                    "verification_status": "unverified",
                    "material_count": 1,
                },
            ],
            "run_info": {
                "mode": "real",
                "provider": "openai",
                "model": "gpt-test",
                "source_pack": "data/replay/coffee-week-2026-09-07/manifest.json",
                "stages_completed": [
                    "read_materials",
                    "resolve_versions",
                    "merge_events",
                    "generate_output",
                    "awaiting_human_review",
                ],
                "started_at": "2026-08-31T09:00:00+08:00",
                "completed_at": "2026-08-31T09:01:00+08:00",
            },
        }

    def parse(self, generated=None, runtime=None) -> BrandRadarWeeklyOutput:
        return parse_brand_radar_output(
            json.dumps(generated if generated is not None else self.generated, ensure_ascii=False),
            **(runtime if runtime is not None else self.runtime),
        )

    def parse_with_trace(self, generated, runtime, trace) -> BrandRadarWeeklyOutput:
        return parse_brand_radar_output(
            json.dumps(generated, ensure_ascii=False),
            **runtime,
            investigation_trace=trace,
        )

    def gap_trace(self, competitors=None) -> dict:
        competitors = competitors or ["库迪咖啡", "Tims 天好中国"]
        return {
            "goal_snapshot": {
                "brand": "瑞幸咖啡",
                "category": "现制咖啡",
                "regions": ["全国", "上海"],
                "competitors": competitors,
                "keywords": ["早餐"],
                "business_question": "下周有哪些值得跟进或待核的信号？",
            },
            "plan_steps": [
                {
                    "step_id": "step-gap",
                    "objective": "确认 Tims 天好中国是否有可用于企划判断的直接材料。",
                }
            ],
            "selected_actions": [
                {
                    "action_id": "action-gap",
                    "step_id": "step-gap",
                    "action_type": "compare_competitor_evidence",
                    "reason": "目标点名竞品但观察包未必覆盖，先确认材料缺口。",
                    "arguments": {"competitor": "Tims 天好中国"},
                    "source_ids": [],
                }
            ],
            "tool_feedback": [
                {
                    "feedback_id": "feedback-gap",
                    "action_id": "action-gap",
                    "source_ids": [],
                    "summary": "当前观察包没有 Tims 天好中国 的直接材料。",
                    "outcome": "no_pack_evidence",
                    "decision_hint": "材料缺口不等于竞品没有动作；只能记录缺证，不能推断市场空位。",
                }
            ],
            "adjustment_reasons": [
                {
                    "adjustment_id": "adjustment-gap",
                    "action_id": "action-gap",
                    "feedback_id": "feedback-gap",
                    "reason": "把竞品缺材料作为待核卡，而不是挂到无关来源。",
                }
            ],
            "generation_attempts": [
                {"attempt": 1, "status": "validated", "issues": []}
            ],
        }

    def assert_invalid(self, generated=None, runtime=None) -> None:
        with self.assertRaises(BrandRadarValidationError):
            self.parse(generated=generated, runtime=runtime)

    def test_valid_output_injects_runtime_metadata(self) -> None:
        result = self.parse()

        self.assertIsInstance(result, BrandRadarWeeklyOutput)
        self.assertEqual(result.schema_version, "1.0")
        self.assertEqual(result.scenario_id, "brand_radar_weekly")
        self.assertEqual(result.run_info.provider, "openai")
        self.assertEqual(result.source_catalog[0].source_id, "source-verified")

    def test_json_fence_is_supported(self) -> None:
        raw = "```json\n" + json.dumps(self.generated, ensure_ascii=False) + "\n```"
        result = parse_brand_radar_output(raw, **self.runtime)
        self.assertEqual(result.human_review.status, "awaiting_human_review")

    def test_invalid_json_never_falls_back_to_raw_text(self) -> None:
        with self.assertRaises(BrandRadarValidationError):
            parse_brand_radar_output("not json", **self.runtime)

    def test_duplicate_source_card_and_brief_ids_are_rejected(self) -> None:
        cases = []

        duplicate_source_runtime = copy.deepcopy(self.runtime)
        duplicate_source_runtime["source_catalog"].append(
            copy.deepcopy(duplicate_source_runtime["source_catalog"][0])
        )
        cases.append((self.generated, duplicate_source_runtime))

        duplicate_card_generated = copy.deepcopy(self.generated)
        duplicate_card_generated["intelligence_cards"][1]["card_id"] = "card-breakfast"
        cases.append((duplicate_card_generated, self.runtime))

        duplicate_brief_generated = copy.deepcopy(self.generated)
        duplicate_brief_generated["briefs"][1]["brief_id"] = "brief-scenario"
        cases.append((duplicate_brief_generated, self.runtime))

        for generated, runtime in cases:
            with self.subTest(generated=generated, runtime=runtime):
                self.assert_invalid(generated=generated, runtime=runtime)

    def test_unknown_and_excluded_sources_are_rejected(self) -> None:
        unknown = copy.deepcopy(self.generated)
        unknown["intelligence_cards"][0]["source_ids"] = ["source-missing"]
        self.assert_invalid(generated=unknown)

        excluded = copy.deepcopy(self.generated)
        excluded["intelligence_cards"][0]["source_ids"] = ["source-expired"]
        self.assert_invalid(generated=excluded)

    def test_invalid_card_references_are_rejected_everywhere(self) -> None:
        paths = [
            ("calendar", 0),
            ("keywords", 0),
            ("briefs", 0),
        ]
        for collection, index in paths:
            generated = copy.deepcopy(self.generated)
            generated[collection][index]["card_ids"] = ["card-missing"]
            with self.subTest(collection=collection):
                self.assert_invalid(generated=generated)

        review = copy.deepcopy(self.generated)
        review["human_review"]["items"][0]["card_ids"] = ["card-missing"]
        self.assert_invalid(generated=review)

    def test_requires_exactly_three_briefs(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["briefs"].pop()
        self.assert_invalid(generated=generated)

    def test_calendar_keywords_and_human_review_cannot_be_empty(self) -> None:
        for path in (("calendar",), ("keywords",), ("human_review", "items")):
            generated = copy.deepcopy(self.generated)
            target = generated
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = []
            with self.subTest(path=path):
                self.assert_invalid(generated=generated)

    def test_every_merged_event_must_be_preserved_in_one_card(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["intelligence_cards"] = [generated["intelligence_cards"][0]]
        generated["briefs"][1]["card_ids"] = ["card-breakfast"]
        generated["human_review"]["items"][0]["card_ids"] = ["card-breakfast"]
        self.assert_invalid(generated=generated)

    def test_requires_distinct_brief_perspectives(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["briefs"][1]["perspective"] = "consumption_scenario"
        self.assert_invalid(generated=generated)

    def test_needs_verification_requires_pending_question(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["intelligence_cards"][1]["pending_questions"] = []
        self.assert_invalid(generated=generated)

    def test_unverified_source_cannot_support_a_definite_card(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["intelligence_cards"][1]["priority"] = "continue_observing"
        self.assert_invalid(generated=generated)

    def test_calendar_date_must_be_inside_runtime_window(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["calendar"][0]["date"] = "2026-10-04"
        self.assert_invalid(generated=generated)

    def test_summary_wording_does_not_block_a_traceable_result(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["executive_summary"] = "库迪咖啡9月10日官宣全国买一送一，瑞幸本周建议立刻跟进。"
        result = self.parse(generated=generated)
        self.assertNotIn("库迪咖啡", result.executive_summary)
        self.assertEqual(
            "本周优先讨论：工作日早餐窗口 "
            "信息还不够，先别放进方案：竞品联名传闻；"
            "先找到能确认它的公开信息再决定。",
            result.executive_summary,
        )

    def test_city_event_card_can_have_no_brand(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["intelligence_cards"][0]["brands"] = []
        result = self.parse(generated=generated)
        self.assertEqual(result.intelligence_cards[0].brands, [])

    def test_no_pack_evidence_feedback_can_support_gap_card_without_sources(self) -> None:
        generated = copy.deepcopy(self.generated)
        runtime = copy.deepcopy(self.runtime)
        runtime["observation_settings"]["competitors"].append("Tims 天好中国")
        gap_card = {
            "card_id": "card-tims-gap",
            "title": "Tims 天好中国缺少直接材料",
            "fact_summary": "本次调查反馈显示观察包没有 Tims 天好中国 的直接材料。",
            "brands": ["Tims 天好中国"],
            "event_date": None,
            "regions": ["全国"],
            "event_type": "competitor_evidence_gap",
            "priority": "needs_verification",
            "why_it_matters": "缺材料不能被写成竞品没有动作，但需要进入企划会提醒。",
            "recommendation": "后续只核查竞品官方渠道，不据此判断市场空位。",
            "risk_notes": ["不得把缺证包装为确定机会。"],
            "pending_questions": ["Tims 天好中国下周是否有公开营销动作？"],
            "source_ids": [],
            "feedback_ids": ["feedback-gap"],
        }
        generated["intelligence_cards"].append(gap_card)
        generated["briefs"][1]["angle"] = "Tims 天好中国缺证时先保留竞品判断空间。"
        generated["briefs"][1]["card_ids"] = ["card-tims-gap"]
        generated["human_review"]["items"].append(
            {
                "review_id": "review-tims-gap",
                "question": "Tims 天好中国是否已有官方公开动作？",
                "card_ids": ["card-tims-gap"],
            }
        )

        for outcome in ("no_pack_evidence", "no_current_pack_evidence"):
            trace = self.gap_trace()
            trace["tool_feedback"][0]["outcome"] = outcome
            with self.subTest(outcome=outcome):
                result = self.parse_with_trace(generated, runtime, trace)
                card = next(
                    item
                    for item in result.intelligence_cards
                    if item.card_id == "card-tims-gap"
                )
                self.assertEqual([], card.source_ids)
                self.assertEqual(["feedback-gap"], card.feedback_ids)

    def test_competitor_mentions_cannot_attach_to_unrelated_card(self) -> None:
        generated = copy.deepcopy(self.generated)
        runtime = copy.deepcopy(self.runtime)
        runtime["observation_settings"]["competitors"].append("Tims 天好中国")
        generated["briefs"][1]["angle"] = "Tims 天好中国缺证时先保留竞品判断空间。"
        generated["briefs"][1]["card_ids"] = ["card-breakfast"]

        with self.assertRaises(BrandRadarValidationError) as raised:
            self.parse_with_trace(generated, runtime, self.gap_trace())

        self.assertIn("Tims 天好中国", str(raised.exception))

    def test_external_actions_must_be_empty(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["human_review"]["external_actions"] = ["send_feishu"]
        self.assert_invalid(generated=generated)

    def test_model_cannot_forge_runtime_metadata(self) -> None:
        for field, forged in (
            ("provider", "forged-provider"),
            ("mode", "mock"),
            ("brand_profile", {"mode": "forged"}),
            ("run_info", {"provider": "forged-provider"}),
            ("source_catalog", []),
            ("schema_version", "999"),
        ):
            generated = copy.deepcopy(self.generated)
            generated[field] = forged
            with self.subTest(field=field):
                self.assert_invalid(generated=generated)

    def test_material_gap_cannot_be_written_as_brand_has_no_action(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["executive_summary"] = "瑞幸咖啡本周无新动作。"
        self.assert_invalid(generated=generated)

    def test_research_next_step_must_name_missing_evidence(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["briefs"][0]["next_step"] = "调研门店周边客流。"
        generated["briefs"][0]["missing_evidence"] = []
        self.assert_invalid(generated=generated)

    def test_schema_prompt_limits_model_owned_fields(self) -> None:
        prompt = get_brand_radar_schema_prompt()
        self.assertIn("external_actions", prompt)
        self.assertIn("source_catalog", prompt)
        self.assertIn("feedback_ids", prompt)
        self.assertIn("no_pack_evidence", prompt)
        self.assertIn("没有执行该竞品调查", prompt)
        self.assertIn("品牌无新动作", prompt)
        self.assertIn("只由程序注入", prompt)
        self.assertIn("每一条 merge_records", prompt)
        self.assertIn("完整保留", prompt)


if __name__ == "__main__":
    unittest.main()
