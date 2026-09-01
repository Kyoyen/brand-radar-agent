from __future__ import annotations

import copy
import json
import inspect
import unittest

import tests.test_brand_radar_output as day_one_fixtures

import framework.brand_radar_output as output_contract
from framework.brand_radar_output import (
    BrandRadarValidationError,
    BrandRadarWeeklyOutput,
    get_brand_radar_schema_prompt,
    parse_brand_radar_output,
)


class InvestigationTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = day_one_fixtures.BrandRadarOutputTests(
            methodName="test_valid_output_injects_runtime_metadata"
        )
        fixture.setUp()
        self.generated = fixture.generated
        self.runtime = fixture.runtime
        self.trace = {
            "goal_snapshot": {
                "brand": "瑞幸咖啡",
                "category": "现制咖啡",
                "regions": ["全国", "上海"],
                "competitors": ["库迪咖啡"],
                "keywords": ["早餐"],
                "business_question": "下周有哪些值得跟进或待核的信号？",
            },
            "plan_steps": [
                {
                    "step_id": "step-competitor-check",
                    "objective": "核对竞品传闻与已有公开材料是否一致。",
                }
            ],
            "selected_actions": [
                {
                    "action_id": "action-competitor",
                    "step_id": "step-competitor-check",
                    "action_type": "compare_competitor_evidence",
                    "reason": "竞品传闻会影响本周差异化判断。",
                    "arguments": {
                        "competitor": "库迪咖啡",
                        "source_ids": ["source-unverified", "source-verified"],
                    },
                    "source_ids": ["source-unverified", "source-verified"],
                }
            ],
            "tool_feedback": [
                {
                    "feedback_id": "feedback-competitor",
                    "action_id": "action-competitor",
                    "source_ids": ["source-unverified", "source-verified"],
                    "summary": "只有人工摘录提到联名，公开材料没有确认。",
                    "outcome": "unverified",
                    "decision_hint": "保留待核，不把传闻写入确定性企划判断。",
                }
            ],
            "adjustment_reasons": [
                {
                    "adjustment_id": "adjustment-competitor",
                    "action_id": "action-competitor",
                    "feedback_id": "feedback-competitor",
                    "reason": "把竞品联名从确定信号调整为待核问题。",
                }
            ],
            "generation_attempts": [
                {"attempt": 1, "status": "validated", "issues": []}
            ],
        }

    def parse(self):
        return parse_brand_radar_output(
            json.dumps(self.generated, ensure_ascii=False),
            investigation_trace=self.trace,
            **self.runtime,
        )

    def trace_1_2(self) -> dict:
        trace = copy.deepcopy(self.trace)
        trace["decision_log"] = [
            {
                "round": 1,
                "decision": "investigate",
                "skill_name": "signal-triage",
                "reason": "先核对竞品材料是否足以支持当前判断。",
                "based_on_feedback_ids": [],
                "action_id": "action-competitor",
            },
            {
                "round": 2,
                "decision": "generate",
                "skill_name": "brief-distillation",
                "reason": "现有反馈足以转译为待核企划角度。",
                "based_on_feedback_ids": ["feedback-competitor"],
                "action_id": None,
            },
        ]
        return trace

    def runtime_1_2(self) -> dict:
        runtime = copy.deepcopy(self.runtime)
        runtime["run_info"]["brand_profile"] = {
            "mode": "custom",
            "file": "memory/brand/BRAND.md",
            "answered_questions": 6,
            "fingerprint": "a" * 64,
        }
        return runtime

    def test_trace_is_runtime_injected_and_schema_is_1_1(self) -> None:
        self.assertIn(
            "investigation_trace",
            inspect.signature(parse_brand_radar_output).parameters,
        )
        self.assertIn(
            '"arguments"',
            json.dumps(BrandRadarWeeklyOutput.model_json_schema()),
        )
        self.assertIn(
            '"decision_hint"',
            json.dumps(BrandRadarWeeklyOutput.model_json_schema()),
        )
        result = self.parse()

        self.assertEqual("1.1", result.schema_version)
        self.assertEqual(
            "compare_competitor_evidence",
            result.investigation_trace.selected_actions[0].action_type,
        )
        self.assertEqual(
            "库迪咖啡",
            result.investigation_trace.selected_actions[0].arguments["competitor"],
        )
        self.assertEqual(
            "保留待核，不把传闻写入确定性企划判断。",
            result.investigation_trace.tool_feedback[0].decision_hint,
        )

    def test_decision_log_upgrades_new_trace_to_1_2_and_keeps_1_1_readable(self) -> None:
        legacy = self.parse()
        current = parse_brand_radar_output(
            json.dumps(self.generated, ensure_ascii=False),
            investigation_trace=self.trace_1_2(),
            **self.runtime_1_2(),
        )

        self.assertEqual("1.1", legacy.schema_version)
        self.assertIsNone(legacy.investigation_trace.decision_log)
        self.assertEqual("1.2", current.schema_version)
        self.assertEqual(
            ["investigate", "generate"],
            [item.decision for item in current.investigation_trace.decision_log],
        )
        self.assertEqual(
            "memory/brand/BRAND.md",
            current.run_info.brand_profile.file,
        )

    def test_1_2_decision_log_must_be_sequential_cumulative_and_end_generate(self) -> None:
        cases = []

        no_generate = self.trace_1_2()
        no_generate["decision_log"].pop()
        cases.append(("end generate", no_generate))

        wrong_round = self.trace_1_2()
        wrong_round["decision_log"][1]["round"] = 3
        cases.append(("sequential round", wrong_round))

        missing_feedback = self.trace_1_2()
        missing_feedback["decision_log"][1]["based_on_feedback_ids"] = []
        cases.append(("cumulative feedback", missing_feedback))

        generate_with_action = self.trace_1_2()
        generate_with_action["decision_log"][1]["action_id"] = "action-competitor"
        cases.append(("generate action", generate_with_action))

        investigate_without_action = self.trace_1_2()
        investigate_without_action["decision_log"][0]["action_id"] = None
        cases.append(("investigate action", investigate_without_action))

        for label, trace in cases:
            with self.subTest(label=label):
                with self.assertRaises(BrandRadarValidationError):
                    parse_brand_radar_output(
                        json.dumps(self.generated, ensure_ascii=False),
                        investigation_trace=trace,
                        **self.runtime_1_2(),
                    )

    def test_1_2_requires_program_owned_brand_profile_metadata(self) -> None:
        with self.assertRaises(BrandRadarValidationError):
            parse_brand_radar_output(
                json.dumps(self.generated, ensure_ascii=False),
                investigation_trace=self.trace_1_2(),
                **self.runtime,
            )

    def test_trace_can_be_validated_before_generation(self) -> None:
        self.assertTrue(hasattr(output_contract, "validate_investigation_preflight"))
        trace = {
            key: copy.deepcopy(self.trace[key])
            for key in (
                "goal_snapshot",
                "plan_steps",
                "selected_actions",
                "tool_feedback",
            )
        }

        validated = output_contract.validate_investigation_preflight(
            trace,
            known_source_ids={"source-verified", "source-unverified", "source-expired"},
        )

        self.assertFalse(hasattr(validated, "adjustment_reasons"))
        self.assertFalse(hasattr(validated, "generation_attempts"))

        trace["tool_feedback"] = []
        with self.assertRaises(BrandRadarValidationError):
            output_contract.validate_investigation_preflight(
                trace,
                known_source_ids={
                    "source-verified",
                    "source-unverified",
                    "source-expired",
                },
            )

    def test_trace_rejects_broken_id_and_source_graphs(self) -> None:
        cases = []

        unknown_step = copy.deepcopy(self.trace)
        unknown_step["selected_actions"][0]["step_id"] = "step-missing"
        cases.append(("unknown step", unknown_step))

        unknown_source = copy.deepcopy(self.trace)
        unknown_source["selected_actions"][0]["source_ids"] = ["source-missing"]
        cases.append(("unknown source", unknown_source))

        duplicate_id = copy.deepcopy(self.trace)
        duplicate_id["adjustment_reasons"][0]["adjustment_id"] = (
            duplicate_id["plan_steps"][0]["step_id"]
        )
        cases.append(("duplicate id", duplicate_id))

        missing_feedback = copy.deepcopy(self.trace)
        missing_feedback["selected_actions"].append(
            {
                "action_id": "action-local",
                "step_id": "step-competitor-check",
                "action_type": "inspect_local_evidence",
                "reason": "补看公开材料原文。",
                "arguments": {"source_ids": ["source-verified"]},
                "source_ids": ["source-verified"],
            }
        )
        cases.append(("one feedback per action", missing_feedback))

        wrong_feedback_sources = copy.deepcopy(self.trace)
        wrong_feedback_sources["tool_feedback"][0]["source_ids"] = ["source-expired"]
        cases.append(("feedback source belongs to action", wrong_feedback_sources))

        wrong_adjustment = copy.deepcopy(self.trace)
        wrong_adjustment["adjustment_reasons"][0]["feedback_id"] = "feedback-missing"
        cases.append(("adjustment references feedback", wrong_adjustment))

        for label, trace in cases:
            with self.subTest(label=label):
                with self.assertRaises(BrandRadarValidationError):
                    output_contract.validate_investigation_trace(
                        trace,
                        known_source_ids={
                            "source-verified",
                            "source-unverified",
                            "source-expired",
                        },
                    )

    def test_generation_attempts_allow_only_one_success_or_one_repair(self) -> None:
        issue = {
            "location": "briefs.2.card_ids",
            "message": "references unknown card",
            "type": "value_error",
        }
        repaired = copy.deepcopy(self.trace)
        repaired["generation_attempts"] = [
            {"attempt": 1, "status": "validation_failed", "issues": [issue]},
            {"attempt": 2, "status": "validated", "issues": []},
        ]
        validated = output_contract.validate_investigation_trace(
            repaired,
            known_source_ids={"source-verified", "source-unverified", "source-expired"},
        )
        self.assertEqual([1, 2], [item.attempt for item in validated.generation_attempts])

        invalid_sequences = [
            [{"attempt": 1, "status": "validation_failed", "issues": []}],
            [{"attempt": 1, "status": "validated", "issues": [issue]}],
            [
                {"attempt": 1, "status": "validated", "issues": []},
                {"attempt": 2, "status": "validated", "issues": []},
            ],
            [{"attempt": 1, "status": "validation_failed", "issues": [issue]}],
            [{"attempt": 2, "status": "validated", "issues": []}],
        ]
        for sequence in invalid_sequences:
            trace = copy.deepcopy(self.trace)
            trace["generation_attempts"] = sequence
            with self.subTest(sequence=sequence):
                with self.assertRaises(BrandRadarValidationError):
                    output_contract.validate_investigation_trace(
                        trace,
                        known_source_ids={
                            "source-verified",
                            "source-unverified",
                            "source-expired",
                        },
                    )

        no_attempt = copy.deepcopy(self.trace)
        no_attempt["generation_attempts"] = []
        with self.assertRaises(BrandRadarValidationError):
            parse_brand_radar_output(
                json.dumps(self.generated, ensure_ascii=False),
                investigation_trace=no_attempt,
                **self.runtime,
            )

    def test_no_evidence_action_can_record_empty_source_ids(self) -> None:
        definitions = BrandRadarWeeklyOutput.model_json_schema()["$defs"]
        self.assertNotIn(
            "minItems",
            definitions["_SelectedAction"]["properties"]["source_ids"],
        )
        self.assertNotIn(
            "minItems",
            definitions["_ToolFeedback"]["properties"]["source_ids"],
        )

        trace = copy.deepcopy(self.trace)
        trace["selected_actions"][0]["source_ids"] = []
        trace["selected_actions"][0]["arguments"] = {"competitor": "库迪咖啡"}
        trace["tool_feedback"][0]["source_ids"] = []
        trace["tool_feedback"][0]["outcome"] = "no_evidence"
        trace["tool_feedback"][0]["summary"] = "观察包内没有库迪咖啡的可用材料。"
        trace["tool_feedback"][0]["decision_hint"] = "保留证据缺口，交由人工决定是否补材料。"

        validated = output_contract.validate_investigation_trace(
            trace,
            known_source_ids={"source-verified", "source-unverified", "source-expired"},
        )

        self.assertEqual([], validated.tool_feedback[0].source_ids)

    def test_unresolved_conflict_can_only_support_a_needs_verification_card(self) -> None:
        status_schema = BrandRadarWeeklyOutput.model_json_schema()["$defs"][
            "_VersionDecision"
        ]["properties"]["status"]
        self.assertIn("unresolved_conflict", status_schema["enum"])

        runtime = copy.deepcopy(self.runtime)
        runtime["version_decisions"][0]["status"] = "unresolved_conflict"
        runtime["version_decisions"][0]["reason"] = "两份有效材料对日期描述冲突。"
        with self.assertRaises(BrandRadarValidationError):
            parse_brand_radar_output(
                json.dumps(self.generated, ensure_ascii=False),
                investigation_trace=self.trace,
                **runtime,
            )

        generated = copy.deepcopy(self.generated)
        generated["intelligence_cards"][0]["priority"] = "needs_verification"
        generated["intelligence_cards"][0]["pending_questions"] = [
            "活动日期应以哪份官方材料为准？"
        ]
        result = parse_brand_radar_output(
            json.dumps(generated, ensure_ascii=False),
            investigation_trace=self.trace,
            **runtime,
        )
        self.assertEqual("needs_verification", result.intelligence_cards[0].priority)

    def test_goal_snapshot_must_match_the_runtime_business_goal(self) -> None:
        trace = copy.deepcopy(self.trace)
        trace["goal_snapshot"]["keywords"] = ["夜咖"]

        with self.assertRaises(BrandRadarValidationError):
            parse_brand_radar_output(
                json.dumps(self.generated, ensure_ascii=False),
                investigation_trace=trace,
                **self.runtime,
            )

    def test_final_parse_rechecks_the_trusted_trace_graph(self) -> None:
        trace = copy.deepcopy(self.trace)
        trace["selected_actions"][0]["source_ids"] = ["source-missing"]
        trace["tool_feedback"][0]["source_ids"] = ["source-missing"]

        with self.assertRaises(BrandRadarValidationError):
            parse_brand_radar_output(
                json.dumps(self.generated, ensure_ascii=False),
                investigation_trace=trace,
                **self.runtime,
            )

    def test_validation_error_exposes_read_only_structured_issues(self) -> None:
        generated = copy.deepcopy(self.generated)
        generated["provider"] = "forged-provider"

        with self.assertRaises(BrandRadarValidationError) as raised:
            parse_brand_radar_output(
                json.dumps(generated, ensure_ascii=False),
                investigation_trace=self.trace,
                **self.runtime,
            )

        self.assertTrue(hasattr(raised.exception, "issues"))
        issues = raised.exception.issues
        self.assertIsInstance(issues, tuple)
        self.assertEqual("provider", issues[0].location)
        self.assertEqual("extra_forbidden", issues[0].type)
        self.assertEqual(
            {
                "location": "provider",
                "message": "Extra inputs are not permitted",
                "type": "extra_forbidden",
            },
            issues[0].as_dict(),
        )
        with self.assertRaises(AttributeError):
            issues[0].message = "mutated"
        with self.assertRaises(AttributeError):
            raised.exception.issues = ()

    def test_model_cannot_forge_the_runtime_investigation_trace(self) -> None:
        self.assertIn("investigation_trace", get_brand_radar_schema_prompt())
        generated = copy.deepcopy(self.generated)
        generated["investigation_trace"] = self.trace

        with self.assertRaises(BrandRadarValidationError):
            parse_brand_radar_output(
                json.dumps(generated, ensure_ascii=False),
                investigation_trace=self.trace,
                **self.runtime,
            )

    def test_action_type_and_arguments_are_fail_closed(self) -> None:
        illegal_action = copy.deepcopy(self.trace)
        illegal_action["selected_actions"][0]["action_type"] = "search_the_web"
        with self.assertRaises(BrandRadarValidationError):
            output_contract.validate_investigation_trace(
                illegal_action,
                known_source_ids={"source-verified", "source-unverified"},
            )

        non_json_arguments = copy.deepcopy(self.trace)
        non_json_arguments["selected_actions"][0]["arguments"] = {
            "unsafe": object()
        }
        with self.assertRaises(BrandRadarValidationError):
            output_contract.validate_investigation_trace(
                non_json_arguments,
                known_source_ids={"source-verified", "source-unverified"},
            )


if __name__ == "__main__":
    unittest.main()
