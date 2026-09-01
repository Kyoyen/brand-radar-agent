from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from framework.agent_runner import AgentRunner


ROOT = Path(__file__).resolve().parents[1]
REPLAY_PACK = ROOT / "data/replay/coffee-week-2026-09-07"
REPLAY_MANIFEST = REPLAY_PACK / "manifest.json"
EXPECTED_RESULT = REPLAY_PACK / "expected-result.json"


class ObservationDrivenLLM:
    is_mock = False
    provider = "observation-script"
    model = "local-planner"

    def __init__(self, planner, result_mutator=None) -> None:
        self._planner = planner
        self._result_mutator = result_mutator or (lambda result, _payload: result)
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        user_content = kwargs["messages"][1]["content"]
        if len(self.calls) == 1:
            payload = _extract_json_after_marker(user_content, "observation_payload：")
            response = self._planner(payload)
        elif len(self.calls) == 2:
            payload = _extract_json_after_marker(user_content, "tool_feedback。")
            result = json.loads(EXPECTED_RESULT.read_text(encoding="utf-8"))
            response = _generation(
                self._result_mutator(result, payload),
                payload["investigation_trace"]["selected_actions"],
            )
        else:
            raise AssertionError("variation acceptance should finish without repair")
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


def _extract_json_after_marker(content: str, marker: str) -> dict:
    start = content.index(marker) + len(marker)
    decoder = json.JSONDecoder()
    tail = content[start:]
    for index, char in enumerate(tail):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(tail[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise AssertionError(f"could not find JSON object after marker: {marker}")


def _plan(action_type: str, reason: str, arguments: dict[str, str]) -> dict:
    return {
        "plan_steps": [
            {
                "step_id": "step-1",
                "objective": reason,
            }
        ],
        "actions": [
            {
                "action_id": "action-1",
                "step_id": "step-1",
                "action_type": action_type,
                "reason": reason,
                "arguments": arguments,
            }
        ],
    }


def _generation(result: dict, actions: list[dict]) -> dict:
    return {
        "adjustment_reasons": [
            {
                "adjustment_id": f"adjustment-{index}",
                "action_id": action["action_id"],
                "feedback_id": f"feedback-{action['action_id']}",
                "reason": "根据本地调查反馈调整或保留周企划判断。",
            }
            for index, action in enumerate(actions, start=1)
        ],
        "result": result,
    }


def _copy_pack_with_manifest(root: Path, mutate_manifest) -> Path:
    pack_root = root / "pack"
    shutil.copytree(REPLAY_PACK / "sources", pack_root / "sources")
    shutil.copy2(EXPECTED_RESULT, pack_root / "expected-result.json")
    manifest = json.loads(REPLAY_MANIFEST.read_text(encoding="utf-8"))
    mutate_manifest(manifest)
    manifest_path = pack_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


class WeeklyAgentVariationAcceptanceTests(unittest.TestCase):
    def test_keyword_goal_change_changes_planned_local_evidence_action(self) -> None:
        def use_mxgp_keyword(manifest: dict) -> None:
            manifest["settings"]["keywords"] = ["赛事", "上海", "通勤动线"]
            manifest["settings"]["business_question"] = (
                "下周瑞幸是否应围绕上海赛事通勤动线准备机会观察？"
            )

        def planner(observation: dict) -> dict:
            keywords = observation["marketing_goal"]["keywords"]
            if "赛事" in keywords:
                return _plan(
                    "inspect_local_evidence",
                    "赛事关键词出现时先核对上海 MXGP 本地材料是否可用。",
                    {"source_id": "src_shanghai_mxgp_2026"},
                )
            return _plan(
                "compare_competitor_evidence",
                "社区空间关键词出现时先核对星巴克竞品材料。",
                {"competitor": "星巴克中国"},
            )

        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = _copy_pack_with_manifest(Path(temporary), use_mxgp_keyword)
            llm = ObservationDrivenLLM(planner)
            output, _ = AgentRunner(llm=llm).run_weekly(
                manifest_path,
                output_dir=Path(temporary) / "outputs",
            )

        action = output.investigation_trace.selected_actions[0]
        feedback = output.investigation_trace.tool_feedback[0]
        self.assertEqual(
            ["赛事", "上海", "通勤动线"],
            output.investigation_trace.goal_snapshot.keywords,
        )
        self.assertEqual("inspect_local_evidence", action.action_type)
        self.assertEqual(
            "src_shanghai_mxgp_2026",
            action.arguments["source_id"],
        )
        self.assertEqual("verified_evidence", feedback.outcome)
        self.assertIn("MXGP", feedback.summary)

    def test_competitor_without_pack_evidence_changes_feedback_and_gap_result(self) -> None:
        def add_tims_as_competitor(manifest: dict) -> None:
            manifest["settings"]["competitors"] = ["星巴克中国", "Tims 天好中国"]
            manifest["settings"]["business_question"] = (
                "下周瑞幸是否存在 Tims 天好中国竞品缺证带来的待核判断？"
            )

        def planner(observation: dict) -> dict:
            gaps = observation["attention_required"]["competitors_without_evidence"]
            competitor = "Tims 天好中国" if "Tims 天好中国" in gaps else "星巴克中国"
            return _plan(
                "compare_competitor_evidence",
                "竞品进入目标但观察包缺少直接材料时先记录证据缺口。",
                {"competitor": competitor},
            )

        def add_gap_to_result(result: dict, payload: dict) -> dict:
            feedback = payload["investigation_trace"]["tool_feedback"][0]
            result["keywords"][0]["keyword"] = "Tims 天好中国缺证"
            result["keywords"][0]["why_it_matters"] = feedback[
                "decision_hint"
            ]
            return result

        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = _copy_pack_with_manifest(Path(temporary), add_tims_as_competitor)
            llm = ObservationDrivenLLM(planner, add_gap_to_result)
            output, _ = AgentRunner(llm=llm).run_weekly(
                manifest_path,
                output_dir=Path(temporary) / "outputs",
            )

        action = output.investigation_trace.selected_actions[0]
        feedback = output.investigation_trace.tool_feedback[0]
        self.assertEqual(
            ["星巴克中国", "Tims 天好中国"],
            output.investigation_trace.goal_snapshot.competitors,
        )
        self.assertEqual("Tims 天好中国", action.arguments["competitor"])
        self.assertEqual([], action.source_ids)
        self.assertEqual("no_pack_evidence", feedback.outcome)
        self.assertIn("不能推断市场空位", feedback.decision_hint)
        self.assertEqual("Tims 天好中国缺证", output.keywords[0].keyword)

    def test_unresolved_version_conflict_changes_planned_cross_check_and_card_status(self) -> None:
        def make_tourism_versions_conflict(manifest: dict) -> None:
            for material in manifest["materials"]:
                if material["source_id"] == "src_shanghai_tourism_full_v2":
                    material["supersedes"] = []
                if material["source_id"] == "src_shanghai_tourism_official_summary_dup":
                    material["duplicate_of"] = None
            manifest["settings"]["business_question"] = (
                "下周瑞幸是否应把上海旅游节冲突材料保留为待核？"
            )

        def planner(observation: dict) -> dict:
            conflicts = observation["attention_required"]["unresolved_version_groups"]
            if "shanghai-tourism-festival-2026" in conflicts:
                return _plan(
                    "cross_check_conflicting_evidence",
                    "上海旅游节同级当前材料互相冲突，先交叉核对事件。",
                    {"event_key": "shanghai-tourism-festival-2026"},
                )
            return _plan(
                "compare_event_versions",
                "上海旅游节存在多版本时先确认当前有效版。",
                {"version_group": "shanghai-tourism-festival-2026"},
            )

        def mark_tourism_as_needs_verification(result: dict, payload: dict) -> dict:
            feedback = payload["investigation_trace"]["tool_feedback"][0]
            card = next(
                item
                for item in result["intelligence_cards"]
                if item["card_id"] == "card_shanghai_tourism_festival_2026"
            )
            card["priority"] = "needs_verification"
            card["recommendation"] = feedback["decision_hint"]
            card["risk_notes"] = [
                "上海旅游节当前观察包存在未解决版本冲突，不能选一份作为当前真值。"
            ]
            card["source_ids"] = [
                "src_shanghai_tourism_full_v2",
                "src_shanghai_tourism_official_summary_dup",
            ]
            return result

        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = _copy_pack_with_manifest(
                Path(temporary),
                make_tourism_versions_conflict,
            )
            llm = ObservationDrivenLLM(planner, mark_tourism_as_needs_verification)
            output, _ = AgentRunner(llm=llm).run_weekly(
                manifest_path,
                output_dir=Path(temporary) / "outputs",
            )

        action = output.investigation_trace.selected_actions[0]
        feedback = output.investigation_trace.tool_feedback[0]
        tourism_card = next(
            item
            for item in output.intelligence_cards
            if item.card_id == "card_shanghai_tourism_festival_2026"
        )
        self.assertEqual("cross_check_conflicting_evidence", action.action_type)
        self.assertEqual(
            "shanghai-tourism-festival-2026",
            action.arguments["event_key"],
        )
        self.assertEqual("unresolved_conflict", feedback.outcome)
        self.assertIn("不能选一份作为当前真值", feedback.decision_hint)
        self.assertEqual("needs_verification", tourism_card.priority)


if __name__ == "__main__":
    unittest.main()
