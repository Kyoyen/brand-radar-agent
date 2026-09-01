from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from framework.agent_runner import (
    AgentRunner,
    _load_marketing_skills,
    get_marketing_skill_catalog,
    get_marketing_skill_content,
)
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


def _decision(
    decision: str,
    skill_name: str,
    objective: str,
    reason: str,
    *,
    action_type: str | None = None,
    arguments: dict[str, str] | None = None,
) -> dict:
    payload = {
        "decision": decision,
        "skill_name": skill_name,
        "objective": objective,
        "reason": reason,
        "action_type": action_type,
        "arguments": arguments or {},
    }
    return payload


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


def _default_two_action_decisions() -> tuple[dict, dict, dict]:
    return (
        _decision(
            "investigate",
            "signal-triage",
            "核对星巴克竞品信号是否足以进入企划会",
            "业务目标要求识别竞品空位，先核对当前包中的竞品材料。",
            action_type="compare_competitor_evidence",
            arguments={"competitor": "星巴克中国"},
        ),
        _decision(
            "investigate",
            "brand-fit",
            "核对上海旅游节多版本材料的有效版本",
            "第一轮反馈确认竞品材料可用，继续核对城市事件版本。",
            action_type="compare_event_versions",
            arguments={"version_group": "shanghai-tourism-festival-2026"},
        ),
        _decision(
            "generate",
            "brief-distillation",
            "把已核反馈转成企划结果",
            "两轮反馈已经覆盖竞品与版本缺口，可以开始生成。",
        ),
    )


class WeeklyAgentLoopTests(unittest.TestCase):
    def test_marketing_skill_catalog_exposes_only_names_and_descriptions(self) -> None:
        catalog = get_marketing_skill_catalog()

        self.assertEqual(
            ["signal-triage", "brand-fit", "brief-distillation"],
            [item["name"] for item in catalog],
        )
        self.assertTrue(all(set(item) == {"name", "description"} for item in catalog))
        serialized_catalog = json.dumps(catalog, ensure_ascii=False)
        self.assertNotIn("只回答一个问题", serialized_catalog)
        self.assertNotIn("逐项对照其中的", serialized_catalog)
        self.assertNotIn("每条 Brief 必须引用", serialized_catalog)

    def test_selected_marketing_skill_returns_full_body_only_for_known_name(self) -> None:
        content = get_marketing_skill_content("brand-fit")

        self.assertIn("BRAND.md", content)
        self.assertIn("不把“热点”自动等同于“机会”", content)
        with self.assertRaisesRegex(ValueError, "未知营销技能"):
            get_marketing_skill_content("unknown-skill")

    def test_marketing_skill_loader_fails_closed_for_invalid_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill_dir = root / "one"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: duplicate\nname: duplicate-again\ndescription: test\n---\nbody",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "重复字段"):
                _load_marketing_skills(root)

            (skill_dir / "SKILL.md").write_text("# no front matter", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "front matter"):
                _load_marketing_skills(root)

            (skill_dir / "SKILL.md").write_text(
                "---\nname: no-description\n---\nbody", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "description"):
                _load_marketing_skills(root)

            second_dir = root / "two"
            second_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: same\ndescription: first\n---\nbody", encoding="utf-8"
            )
            (second_dir / "SKILL.md").write_text(
                "---\nname: same\ndescription: second\n---\nbody", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "重复技能 name"):
                _load_marketing_skills(root)

            (second_dir / "SKILL.md").write_bytes(b"x" * 16_385)
            with self.assertRaisesRegex(ValueError, "大小"):
                _load_marketing_skills(root)

    def test_marketing_skill_loader_accepts_only_the_documented_metadata_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill_dir = root / "one"
            skill_dir.mkdir()
            skill_path = skill_dir / "SKILL.md"

            invalid_metadata = (
                "---\nname: [\ndescription: valid\n---\nbody",
                "---\nname: valid-name\ndescription: \"未闭合\n---\nbody",
                "---\nname: \ndescription: valid\n---\nbody",
                "---\nname: valid-name\ndescription: [structured]\n---\nbody",
                "---\nname: valid-name\ndescription: valid\nextra: no\n---\nbody",
            )
            for text in invalid_metadata:
                skill_path.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "只支持"):
                    _load_marketing_skills(root)

            skill_path.write_text(
                "---\nname: valid-name\ndescription: valid\n---\n\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "正文不能为空"):
                _load_marketing_skills(root)

    def test_marketing_skill_loader_enforces_exact_size_limit_and_one_level_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill_dir = root / "one"
            skill_dir.mkdir()
            header = "---\nname: valid-name\ndescription: valid\n---\n"
            exact_limit = header + "x" * (16 * 1024 - len(header))
            skill_path = skill_dir / "SKILL.md"
            skill_path.write_text(exact_limit, encoding="utf-8")
            self.assertEqual(
                ["valid-name"],
                [skill.name for skill in _load_marketing_skills(root)],
            )

            skill_path.write_text(exact_limit + "x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "大小"):
                _load_marketing_skills(root)

            skill_path.write_text(header + "body", encoding="utf-8")
            (root / "SKILL.md").write_text("not scanned", encoding="utf-8")
            nested = skill_dir / "nested"
            nested.mkdir()
            (nested / "SKILL.md").write_text("not scanned", encoding="utf-8")
            self.assertEqual(
                ["valid-name"],
                [skill.name for skill in _load_marketing_skills(root)],
            )

    def test_real_weekly_executes_only_selected_actions_and_persists_feedback(self) -> None:
        llm = ScriptedRealLLM(
            *_default_two_action_decisions(),
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
        self.assertEqual(4, len(llm.calls))
        self.assertEqual("1.2", output.schema_version)
        self.assertEqual(
            ["compare_competitor_evidence", "compare_event_versions"],
            [item.action_type for item in trace.selected_actions],
        )
        self.assertEqual(
            ["step-1", "step-2"],
            [item.step_id for item in trace.plan_steps],
        )
        self.assertEqual(
            ["action-1", "action-2"],
            [item.action_id for item in trace.selected_actions],
        )
        self.assertEqual(
            ["feedback-action-1", "feedback-action-2"],
            [item.feedback_id for item in trace.tool_feedback],
        )
        self.assertEqual(
            ["investigate", "investigate", "generate"],
            [item.decision for item in trace.decision_log],
        )
        self.assertEqual([], trace.decision_log[0].based_on_feedback_ids)
        self.assertEqual(
            ["feedback-action-1"],
            trace.decision_log[1].based_on_feedback_ids,
        )
        self.assertEqual(
            ["feedback-action-1", "feedback-action-2"],
            trace.decision_log[2].based_on_feedback_ids,
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

        first_decision_prompt = llm.calls[0]["messages"][1]["content"]
        second_decision_prompt = llm.calls[1]["messages"][1]["content"]
        final_decision_prompt = llm.calls[2]["messages"][1]["content"]
        generation_prompt = llm.calls[3]["messages"][1]["content"]
        generation_system = llm.calls[3]["messages"][0]["content"]
        self.assertIn("open_questions", first_decision_prompt)
        self.assertIn("compare_competitor_evidence", first_decision_prompt)
        self.assertNotIn("feedback-action-1", first_decision_prompt)
        self.assertIn("feedback-action-1", second_decision_prompt)
        self.assertNotIn("feedback-action-2", second_decision_prompt)
        self.assertIn("feedback-action-1", final_decision_prompt)
        self.assertIn("feedback-action-2", final_decision_prompt)
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
            *_default_two_action_decisions(),
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

        self.assertEqual(5, len(llm.calls))
        self.assertEqual([output_path], artifacts)
        self.assertEqual([], leftovers)
        self.assertEqual(
            [(1, "validation_failed"), (2, "validated")],
            [(item.attempt, item.status) for item in output.investigation_trace.generation_attempts],
        )
        repair_prompt = llm.calls[4]["messages"][1]["content"]
        repair_system = llm.calls[4]["messages"][0]["content"]
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
            *_default_two_action_decisions(),
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

        self.assertEqual(5, len(llm.calls))
        self.assertEqual([output_path], artifacts)
        attempts = output.investigation_trace.generation_attempts
        self.assertEqual("validation_failed", attempts[0].status)
        self.assertEqual("investigation_trace", attempts[0].issues[0].location)
        self.assertEqual("validated", attempts[1].status)

    def test_every_decision_generation_and_repair_receives_brand_runtime_and_skills(self) -> None:
        invalid = _candidate()
        invalid["briefs"] = invalid["briefs"][:2]
        first_decision, _, final_decision = _default_two_action_decisions()
        llm = ScriptedRealLLM(
            first_decision,
            final_decision,
            _generation(invalid, action_count=1),
            _generation(_candidate(), action_count=1),
        )
        custom_brand = """# 测试品牌档案

## 1. 希望被怎样记住
测试品牌必须可靠。
## 2. 最重要的人与场景
服务通勤人群。
## 3. 承诺与可信依据
只依据可核来源。
## 4. 声音与反例
表达克制。
## 5. 热点与竞品判断
不因热度自动跟进。
## 6. 红线与人工确认
外发必须人工确认。
"""
        runtime_rules = "# 测试运行规则\n\n每轮只能做一个本地动作。\n"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            brand_file = root / "BRAND.md"
            agents_file = root / "AGENTS.md"
            brand_file.write_text(custom_brand, encoding="utf-8")
            agents_file.write_text(runtime_rules, encoding="utf-8")
            output, _ = AgentRunner(
                llm=llm,
                brand_file=brand_file,
                runtime_agents_file=agents_file,
            ).run_weekly(
                REPLAY_MANIFEST,
                output_dir=root / "outputs",
            )

        self.assertEqual(4, len(llm.calls))
        for call in llm.calls:
            full_prompt = "\n".join(
                message["content"] for message in call["messages"]
            )
            self.assertIn("测试品牌必须可靠", full_prompt)
            self.assertIn("每轮只能做一个本地动作", full_prompt)
        self.assertIn(
            "信号值不值得继续查",
            llm.calls[1]["messages"][1]["content"],
        )
        self.assertIn(
            "三条可进入创意会讨论的 Brief",
            llm.calls[2]["messages"][1]["content"],
        )
        self.assertIn(
            "三条可进入创意会讨论的 Brief",
            llm.calls[3]["messages"][1]["content"],
        )
        self.assertEqual("custom", output.run_info.brand_profile.mode)
        self.assertEqual(str(brand_file), output.run_info.brand_profile.file)
        self.assertEqual(6, output.run_info.brand_profile.answered_questions)
        self.assertEqual(64, len(output.run_info.brand_profile.fingerprint))

    def test_generate_before_any_action_fails_without_artifact(self) -> None:
        early_generate = _decision(
            "generate",
            "brief-distillation",
            "立即生成",
            "尚未调查但尝试直接生成。",
        )
        llm = ScriptedRealLLM(early_generate)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            with self.assertRaisesRegex(WeeklyPipelineError, "至少完成一次调查"):
                AgentRunner(llm=llm).run_weekly(
                    REPLAY_MANIFEST,
                    output_dir=output_dir,
                )
            leftovers = list(output_dir.glob("*")) if output_dir.exists() else []

        self.assertEqual(1, len(llm.calls))
        self.assertEqual([], leftovers)

    def test_fourth_action_after_three_feedbacks_fails_without_artifact(self) -> None:
        decisions = [
            _decision(
                "investigate",
                "signal-triage",
                "检查一份当前材料",
                "先确认本地证据。",
                action_type="inspect_local_evidence",
                arguments={"source_id": "src_shanghai_mxgp_2026"},
            ),
            _decision(
                "investigate",
                "brand-fit",
                "核对竞品材料",
                "第一轮反馈后继续核对竞品。",
                action_type="compare_competitor_evidence",
                arguments={"competitor": "星巴克中国"},
            ),
            _decision(
                "investigate",
                "signal-triage",
                "核对事件版本",
                "前两轮反馈后仍需确认版本。",
                action_type="compare_event_versions",
                arguments={"version_group": "shanghai-tourism-festival-2026"},
            ),
            _decision(
                "investigate",
                "brand-fit",
                "尝试第四项调查",
                "第三次反馈后仍不收敛。",
                action_type="cross_check_conflicting_evidence",
                arguments={"event_key": "manual-shanghai-coffee-popup-20260912"},
            ),
        ]
        llm = ScriptedRealLLM(*decisions)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            with self.assertRaisesRegex(WeeklyPipelineError, "第三次反馈后必须.*generate"):
                AgentRunner(llm=llm).run_weekly(
                    REPLAY_MANIFEST,
                    output_dir=output_dir,
                )
            leftovers = list(output_dir.glob("*")) if output_dir.exists() else []

        self.assertEqual(4, len(llm.calls))
        fourth_prompt = llm.calls[3]["messages"][1]["content"]
        self.assertIn("feedback-action-1", fourth_prompt)
        self.assertIn("feedback-action-2", fourth_prompt)
        self.assertIn("feedback-action-3", fourth_prompt)
        self.assertEqual([], leftovers)

    def test_generate_decision_cannot_smuggle_action_arguments(self) -> None:
        first_decision, _, _ = _default_two_action_decisions()
        invalid_generate = _decision(
            "generate",
            "brief-distillation",
            "生成企划",
            "尝试在生成时夹带第四动作。",
            action_type="inspect_local_evidence",
            arguments={"source_id": "src_shanghai_mxgp_2026"},
        )
        llm = ScriptedRealLLM(first_decision, invalid_generate)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            with self.assertRaisesRegex(WeeklyPipelineError, "调查决策"):
                AgentRunner(llm=llm).run_weekly(
                    REPLAY_MANIFEST,
                    output_dir=output_dir,
                )
            leftovers = list(output_dir.glob("*")) if output_dir.exists() else []

        self.assertEqual(2, len(llm.calls))
        self.assertEqual([], leftovers)

    def test_competitor_action_reason_cannot_claim_other_competitors(self) -> None:
        overclaimed_decision = _decision(
            "investigate",
            "signal-triage",
            "核对库迪咖啡材料缺口",
            "核对库迪咖啡、Manner、麦咖啡是否都有证据。",
            action_type="compare_competitor_evidence",
            arguments={"competitor": "库迪咖啡"},
        )
        llm = ScriptedRealLLM(overclaimed_decision)
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
            *_default_two_action_decisions(),
            _generation(copy.deepcopy(invalid), action_count=2),
            _generation(copy.deepcopy(invalid), action_count=2),
        )
        runner = AgentRunner(llm=llm)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            with self.assertRaises(BrandRadarValidationError):
                runner.run_weekly(REPLAY_MANIFEST, output_dir=output_dir)
            leftovers = list(output_dir.glob("*")) if output_dir.exists() else []

        self.assertEqual(5, len(llm.calls))
        self.assertEqual([], leftovers)

    def test_request_failure_is_not_repaired_or_downgraded_to_mock(self) -> None:
        request_error = LLMRequestError(
            "authentication", "scripted-provider", "scripted-model"
        )
        decisions = _default_two_action_decisions()
        llm = ScriptedRealLLM(decisions[0], request_error)
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
        invalid_decision = _decision(
            "investigate",
            "signal-triage",
            "向外部平台发送结果",
            "越权动作必须被拒绝。",
            action_type="send_feishu",
            arguments={"chat": "marketing"},
        )
        llm = ScriptedRealLLM(invalid_decision)
        runner = AgentRunner(llm=llm)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            with self.assertRaisesRegex(WeeklyPipelineError, "调查决策"):
                runner.run_weekly(REPLAY_MANIFEST, output_dir=output_dir)
            leftovers = list(output_dir.glob("*")) if output_dir.exists() else []

        self.assertEqual(1, len(llm.calls))
        self.assertEqual([], leftovers)


if __name__ == "__main__":
    unittest.main()
