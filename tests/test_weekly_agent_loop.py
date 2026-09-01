from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from framework.agent_runner import AgentRunner
from framework.brand_radar_output import BrandRadarValidationError
from framework.llm_client import LLMRequestError
from scenarios.brand_radar_weekly import WeeklyPipelineError


ROOT = Path(__file__).resolve().parents[1]
REPLAY_MANIFEST = ROOT / "data/replay/coffee-week-2026-09-07/manifest.json"
EXPECTED_RESULT = REPLAY_MANIFEST.parent / "expected-result.json"


class ScriptedRealLLM:
    is_mock = False
    provider = "scripted-provider"
    model = "scripted-model"

    def __init__(self, *responses: dict | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("Agent made more model calls than the bounded script allows")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(response, ensure_ascii=False)
                    ),
                    finish_reason="stop",
                )
            ]
        )


def _plan(*actions: dict) -> dict:
    return {
        "plan_steps": [
            {
                "step_id": f"step-{index}",
                "objective": action.pop("objective"),
            }
            for index, action in enumerate(actions, start=1)
        ],
        "actions": [
            {
                "action_id": f"action-{index}",
                "step_id": f"step-{index}",
                **action,
            }
            for index, action in enumerate(actions, start=1)
        ],
    }


def _candidate() -> dict:
    return json.loads(EXPECTED_RESULT.read_text(encoding="utf-8"))


def _generation(candidate: dict, action_count: int) -> dict:
    return {
        "adjustment_reasons": [
            {
                "adjustment_id": f"adjustment-{index}",
                "action_id": f"action-{index}",
                "feedback_id": f"feedback-action-{index}",
                "reason": "依据本地调查反馈保留来源约束，并据此确定卡片优先级。",
            }
            for index in range(1, action_count + 1)
        ],
        "result": candidate,
    }


def _default_two_action_plan() -> dict:
    return _plan(
        {
            "objective": "核对星巴克竞品信号是否足以进入企划会",
            "action_type": "compare_competitor_evidence",
            "reason": "业务目标要求识别竞品空位，先核对当前包中的竞品材料。",
            "arguments": {"competitor": "星巴克中国"},
        },
        {
            "objective": "核对上海旅游节多版本材料的有效版本",
            "action_type": "compare_event_versions",
            "reason": "同一事件存在多版本和重复材料，需要确认可用证据。",
            "arguments": {"version_group": "shanghai-tourism-festival-2026"},
        },
    )


class WeeklyAgentLoopTests(unittest.TestCase):
    def test_real_weekly_executes_only_selected_actions_and_persists_feedback(self) -> None:
        llm = ScriptedRealLLM(
            _default_two_action_plan(),
            _generation(_candidate(), action_count=2),
        )
        runner = AgentRunner(llm=llm)
        custom_goal = "请优先判断上海城市事件与星巴克竞品信号如何进入下周企划会"

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            output, output_path = runner.run_weekly(
                REPLAY_MANIFEST,
                task_description=custom_goal,
                output_dir=output_dir,
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            leftovers = list(output_dir.glob("*.tmp"))

        trace = output.investigation_trace
        self.assertEqual(2, len(llm.calls))
        self.assertEqual(
            ["compare_competitor_evidence", "compare_event_versions"],
            [item.action_type for item in trace.selected_actions],
        )
        self.assertEqual(2, len(trace.tool_feedback))
        self.assertEqual(2, len(trace.adjustment_reasons))
        self.assertEqual("validated", trace.generation_attempts[0].status)
        self.assertEqual(custom_goal, trace.goal_snapshot.business_question)
        self.assertEqual(custom_goal, output.observation_settings.business_question)
        self.assertEqual("awaiting_human_review", output.human_review.status)
        self.assertEqual([], output.human_review.external_actions)
        self.assertEqual([], leftovers)
        self.assertIn("investigation_trace", saved)

        planning_prompt = llm.calls[0]["messages"][1]["content"]
        generation_prompt = llm.calls[1]["messages"][1]["content"]
        generation_system = llm.calls[1]["messages"][0]["content"]
        self.assertIn("open_questions", planning_prompt)
        self.assertIn("compare_competitor_evidence", planning_prompt)
        self.assertIn("每个 action.reason 只能描述该动作自己的目标", llm.calls[0]["messages"][0]["content"])
        self.assertIn("tool_feedback", generation_prompt)
        self.assertIn("decision_hint", generation_prompt)
        self.assertNotIn("expected-result.json", generation_prompt)
        self.assertIn("外层顶级字段只能是 adjustment_reasons 和 result", generation_system)
        self.assertIn("根对象.adjustment_reasons", generation_system)
        self.assertIn("根对象.result", generation_system)
        self.assertNotIn('"intelligence_cards": []', generation_system)
        self.assertNotIn(
            "顶层只能包含 executive_summary、intelligence_cards",
            generation_system,
        )

    def test_first_validation_failure_gets_one_repair_then_writes_one_artifact(self) -> None:
        invalid = _candidate()
        invalid["briefs"] = invalid["briefs"][:2]
        llm = ScriptedRealLLM(
            _default_two_action_plan(),
            _generation(invalid, action_count=2),
            _generation(_candidate(), action_count=2),
        )
        runner = AgentRunner(llm=llm)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            output, output_path = runner.run_weekly(
                REPLAY_MANIFEST,
                output_dir=output_dir,
            )
            artifacts = list(output_dir.glob("*.json"))
            leftovers = list(output_dir.glob("*.tmp"))

        self.assertEqual(3, len(llm.calls))
        self.assertEqual([output_path], artifacts)
        self.assertEqual([], leftovers)
        self.assertEqual(
            [(1, "validation_failed"), (2, "validated")],
            [(item.attempt, item.status) for item in output.investigation_trace.generation_attempts],
        )
        repair_prompt = llm.calls[2]["messages"][1]["content"]
        repair_system = llm.calls[2]["messages"][0]["content"]
        repair_payload = json.loads(repair_prompt)
        self.assertIn("validation_issues", repair_prompt)
        self.assertIn("briefs", repair_prompt)
        self.assertNotIn("Traceback", repair_prompt)
        self.assertIn("外层顶级字段只能是 adjustment_reasons 和 result", repair_system)
        self.assertIn("source_catalog", repair_payload["validation_context"])
        self.assertIn("merge_records", repair_payload["generation_evidence"])
        self.assertIn("investigation_trace", repair_payload["generation_evidence"])
        self.assertNotIn('"intelligence_cards": []', repair_system)
        self.assertIn("result 字段 JSON Schema", repair_system)

    def test_model_owned_trace_error_gets_the_same_single_repair(self) -> None:
        invalid_trace_generation = _generation(_candidate(), action_count=2)
        invalid_trace_generation["adjustment_reasons"][0]["adjustment_id"] = "action-1"
        llm = ScriptedRealLLM(
            _default_two_action_plan(),
            invalid_trace_generation,
            _generation(_candidate(), action_count=2),
        )
        runner = AgentRunner(llm=llm)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            output, output_path = runner.run_weekly(
                REPLAY_MANIFEST,
                output_dir=output_dir,
            )
            artifacts = list(output_dir.glob("*.json"))

        self.assertEqual(3, len(llm.calls))
        self.assertEqual([output_path], artifacts)
        attempts = output.investigation_trace.generation_attempts
        self.assertEqual("validation_failed", attempts[0].status)
        self.assertEqual("investigation_trace", attempts[0].issues[0].location)
        self.assertEqual("validated", attempts[1].status)

    def test_competitor_action_reason_cannot_claim_other_competitors(self) -> None:
        overclaimed_plan = _plan(
            {
                "objective": "核对库迪咖啡材料缺口",
                "action_type": "compare_competitor_evidence",
                "reason": "核对库迪咖啡、Manner、麦咖啡是否都有证据。",
                "arguments": {"competitor": "库迪咖啡"},
            },
        )
        llm = ScriptedRealLLM(overclaimed_plan)
        runner = AgentRunner(llm=llm)

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(WeeklyPipelineError) as raised:
                runner.run_weekly(
                    REPLAY_MANIFEST,
                    output_dir=Path(temporary) / "outputs",
                )

        self.assertEqual(1, len(llm.calls))
        self.assertIn("Manner", str(raised.exception))

    def test_second_validation_failure_stops_without_artifact_or_third_generation(self) -> None:
        invalid = _candidate()
        invalid["human_review"]["external_actions"] = ["send_feishu"]
        llm = ScriptedRealLLM(
            _default_two_action_plan(),
            _generation(copy.deepcopy(invalid), action_count=2),
            _generation(copy.deepcopy(invalid), action_count=2),
        )
        runner = AgentRunner(llm=llm)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            with self.assertRaises(BrandRadarValidationError):
                runner.run_weekly(REPLAY_MANIFEST, output_dir=output_dir)
            leftovers = list(output_dir.glob("*")) if output_dir.exists() else []

        self.assertEqual(3, len(llm.calls))
        self.assertEqual([], leftovers)

    def test_request_failure_is_not_repaired_or_downgraded_to_mock(self) -> None:
        request_error = LLMRequestError(
            "authentication", "scripted-provider", "scripted-model"
        )
        llm = ScriptedRealLLM(_default_two_action_plan(), request_error)
        runner = AgentRunner(llm=llm)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            with self.assertRaises(LLMRequestError) as raised:
                runner.run_weekly(REPLAY_MANIFEST, output_dir=output_dir)
            leftovers = list(output_dir.glob("*")) if output_dir.exists() else []

        self.assertIs(request_error, raised.exception)
        self.assertEqual(2, len(llm.calls))
        self.assertEqual([], leftovers)

    def test_unknown_investigation_action_fails_closed_before_generation(self) -> None:
        invalid_plan = _plan(
            {
                "objective": "向外部平台发送结果",
                "action_type": "send_feishu",
                "reason": "越权动作必须被拒绝。",
                "arguments": {"chat": "marketing"},
            }
        )
        llm = ScriptedRealLLM(invalid_plan)
        runner = AgentRunner(llm=llm)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            with self.assertRaisesRegex(WeeklyPipelineError, "调查计划"):
                runner.run_weekly(REPLAY_MANIFEST, output_dir=output_dir)
            leftovers = list(output_dir.glob("*")) if output_dir.exists() else []

        self.assertEqual(1, len(llm.calls))
        self.assertEqual([], leftovers)


if __name__ == "__main__":
    unittest.main()
