from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from framework.agent_runner import AgentRunner
from framework.llm_client import LLMClient, LLMConfigurationError, LLMRequestError
from scenarios.brand_radar_weekly import (
    INVESTIGATION_ACTION_NAMES,
    INVESTIGATION_TOOLS,
    WEEKLY_TOOL_ORDER,
    WEEKLY_TOOLS,
    WeeklyScenarioRuntime,
    WeeklySourcePackError,
)


ROOT = Path(__file__).resolve().parents[1]
REPLAY_MANIFEST = ROOT / "data/replay/coffee-week-2026-09-07/manifest.json"

TOURISM_OLD = "src_shanghai_tourism_summer_preview_v1"
TOURISM_CURRENT = "src_shanghai_tourism_full_v2"
TOURISM_DUPLICATE = "src_shanghai_tourism_official_summary_dup"
MANUAL_UNVERIFIED = "src_manual_shanghai_coffee_popup_20260912"
COFFEE_2025_EXPIRED = "src_shanghai_coffee_festival_2025_expired"


class FakeLLM:
    def __init__(self, *, is_mock: bool, error: Exception | None = None) -> None:
        self.is_mock = is_mock
        self.provider = "fake-provider"
        self.model = "fake-model"
        self.error = error
        self.chat_calls = 0

    def chat(self, **_kwargs):
        self.chat_calls += 1
        if self.error is not None:
            raise self.error
        raise AssertionError("Mock weekly runs must load expected-result.json, not call chat()")


class SuccessfulRealLLM:
    is_mock = False
    provider = "fake-real-provider"
    model = "fake-real-model"

    def __init__(self) -> None:
        self.chat_calls = 0
        self.last_messages = []
        self.calls = []

    def chat(self, **kwargs):
        self.chat_calls += 1
        self.last_messages = kwargs["messages"]
        self.calls.append(kwargs)
        if self.chat_calls == 1:
            payload = {
                "plan_steps": [
                    {
                        "step_id": "step-1",
                        "objective": "核对星巴克信号是否足以进入企划会",
                    }
                ],
                "actions": [
                    {
                        "action_id": "action-1",
                        "step_id": "step-1",
                        "action_type": "compare_competitor_evidence",
                        "reason": "竞品对比是本周业务问题的必要查证。",
                        "arguments": {"competitor": "星巴克中国"},
                    }
                ],
            }
        elif self.chat_calls == 2:
            result = json.loads(
                (REPLAY_MANIFEST.parent / "expected-result.json").read_text(
                    encoding="utf-8"
                )
            )
            payload = {
                "adjustment_reasons": [
                    {
                        "adjustment_id": "adjustment-1",
                        "action_id": "action-1",
                        "feedback_id": "feedback-action-1",
                        "reason": "竞品反馈确认存在可引用材料，据此保留竞品卡。",
                    }
                ],
                "result": result,
            }
        else:
            raise AssertionError("Successful weekly run must use exactly two model calls")
        content = json.dumps(payload, ensure_ascii=False)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content),
                    finish_reason="stop",
                )
            ]
        )


def _minimal_manifest() -> dict:
    return {
        "schema_version": "1.0",
        "pack_id": "test-weekly-pack",
        "pack_mode": "REPLAY",
        "settings": {
            "brand": "瑞幸咖啡",
            "category": "现制咖啡",
            "regions": ["全国"],
            "competitors": ["星巴克中国"],
            "keywords": ["咖啡"],
            "business_question": "下周有哪些值得观察的营销信号？",
            "observation_window": {"start": "2026-09-07", "end": "2026-09-13"},
            "calendar_window": {"start": "2026-09-07", "end": "2026-10-06"},
            "safety_boundaries": ["默认停在人工复核前"],
            "review_deadline": "2026-09-04",
        },
        "materials": [
            {
                "source_id": "source-a",
                "title": "测试材料 A",
                "source_type": "REPLAY",
                "source_date": "2026-09-01",
                "url": None,
                "file": "sources/a.md",
                "event_key": "event-a",
                "version_group": "event-a",
                "version_rank": 1,
                "supersedes": [],
                "duplicate_of": None,
                "valid_from": "2026-09-01",
                "valid_to": "2026-09-30",
                "verification_status": "verified",
                "brands": ["瑞幸咖啡"],
                "regions": ["全国"],
            }
        ],
    }


def _write_pack(
    directory: Path,
    manifest: dict | None = None,
    *,
    write_source: bool = True,
) -> Path:
    pack_root = directory / "pack"
    pack_root.mkdir(parents=True)
    data = copy.deepcopy(manifest or _minimal_manifest())
    if write_source:
        source_path = pack_root / data["materials"][0]["file"]
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("# Replay test material\n\nLocal and reviewable.", encoding="utf-8")
    manifest_path = pack_root / "manifest.json"
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def _run_all_weekly_tools(runtime: WeeklyScenarioRuntime) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for tool_name in WEEKLY_TOOL_ORDER:
        result = json.loads(runtime.execute(tool_name, {}))
        if "error" in result:
            raise AssertionError(f"{tool_name} failed unexpectedly: {result['error']}")
        results[tool_name] = result
    return results


class WeeklyReplayRuntimeTests(unittest.TestCase):
    def test_official_replay_pack_resolves_versions_merges_and_exclusions(self) -> None:
        runtime = WeeklyScenarioRuntime(REPLAY_MANIFEST)
        results = _run_all_weekly_tools(runtime)

        materials = results["read_weekly_source_pack"]
        self.assertEqual(10, len(materials["read_success"]))
        self.assertEqual([], materials["read_failed"])
        self.assertEqual(10, len(materials["materials"]))
        self.assertTrue(all(item["content"].strip() for item in materials["materials"]))

        decisions = {
            item["source_id"]: item
            for item in results["resolve_weekly_versions"]["decisions"]
        }
        self.assertEqual("superseded", decisions[TOURISM_OLD]["status"])
        self.assertEqual(TOURISM_CURRENT, decisions[TOURISM_OLD]["effective_source_id"])
        self.assertIn("有效期已", decisions[TOURISM_OLD]["reason"])
        self.assertEqual("duplicate", decisions[TOURISM_DUPLICATE]["status"])
        self.assertEqual(TOURISM_CURRENT, decisions[TOURISM_DUPLICATE]["effective_source_id"])
        self.assertEqual("unverified", decisions[MANUAL_UNVERIFIED]["status"])
        self.assertEqual("expired", decisions[COFFEE_2025_EXPIRED]["status"])

        events = results["merge_weekly_events"]["events"]
        event_keys = [event["event_key"] for event in events]
        self.assertEqual(len(event_keys), len(set(event_keys)))
        tourism_events = [
            event for event in events if event["event_key"] == "shanghai-tourism-festival-2026"
        ]
        self.assertEqual(1, len(tourism_events))
        self.assertEqual(
            {TOURISM_CURRENT, TOURISM_DUPLICATE},
            set(tourism_events[0]["source_ids"]),
        )
        self.assertEqual(2, tourism_events[0]["material_count"])
        self.assertNotIn(
            TOURISM_OLD,
            {source_id for event in events for source_id in event["source_ids"]},
        )

        validator_payload = runtime.validator_payload()
        excluded_ids = {
            item["source_id"] for item in validator_payload["material_log"]["excluded"]
        }
        self.assertEqual({TOURISM_OLD, COFFEE_2025_EXPIRED}, excluded_ids)
        self.assertNotIn(TOURISM_DUPLICATE, excluded_ids)
        self.assertNotIn(MANUAL_UNVERIFIED, excluded_ids)

    def test_illegal_source_type_is_rejected(self) -> None:
        manifest = _minimal_manifest()
        manifest["materials"][0]["source_type"] = "REMOTE"
        with tempfile.TemporaryDirectory() as temporary:
            path = _write_pack(Path(temporary), manifest)
            with self.assertRaisesRegex(WeeklySourcePackError, "source_type.*非法"):
                WeeklyScenarioRuntime(path)

    def test_duplicate_source_id_is_rejected(self) -> None:
        manifest = _minimal_manifest()
        manifest["materials"].append(copy.deepcopy(manifest["materials"][0]))
        with tempfile.TemporaryDirectory() as temporary:
            path = _write_pack(Path(temporary), manifest)
            with self.assertRaisesRegex(WeeklySourcePackError, "source_id 重复"):
                WeeklyScenarioRuntime(path)

    def test_source_path_cannot_escape_pack_root(self) -> None:
        manifest = _minimal_manifest()
        manifest["materials"][0]["file"] = "../outside.md"
        with tempfile.TemporaryDirectory() as temporary:
            path = _write_pack(Path(temporary), manifest, write_source=False)
            with self.assertRaisesRegex(WeeklySourcePackError, "观察包目录之外"):
                WeeklyScenarioRuntime(path)

    def test_missing_source_is_read_failed_without_crashing_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = _write_pack(Path(temporary), write_source=False)
            runtime = WeeklyScenarioRuntime(path)
            results = _run_all_weekly_tools(runtime)

        material_result = results["read_weekly_source_pack"]
        self.assertEqual([], material_result["read_success"])
        self.assertEqual("source-a", material_result["read_failed"][0]["source_id"])
        self.assertIn("材料读取失败", material_result["read_failed"][0]["reason"])
        decision = results["resolve_weekly_versions"]["decisions"][0]
        self.assertEqual("failed", decision["status"])
        self.assertEqual([], results["merge_weekly_events"]["events"])
        self.assertEqual(
            ["source-a"],
            [item["source_id"] for item in runtime.validator_payload()["material_log"]["excluded"]],
        )

    def test_out_of_order_stage_returns_error_and_does_not_advance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = _write_pack(Path(temporary))
            runtime = WeeklyScenarioRuntime(path)
            out_of_order = json.loads(runtime.execute("read_weekly_source_pack", {}))
            first_stage = json.loads(runtime.execute("read_weekly_settings", {}))

        self.assertIn("error", out_of_order)
        self.assertIn("阶段顺序错误", out_of_order["error"])
        self.assertEqual("test-weekly-pack", first_stage["pack_id"])


class WeeklyRunnerTests(unittest.TestCase):
    def test_deepseek_v4_uses_non_thinking_mode_for_json_generation(self) -> None:
        captured: dict = {}

        class FakeCompletions:
            def create(self, **kwargs):
                captured.update(kwargs)
                return "response"

        client = object.__new__(LLMClient)
        client.provider = "deepseek"
        client.model = "deepseek-v4-flash"
        client._client = SimpleNamespace(
            chat=SimpleNamespace(completions=FakeCompletions())
        )

        response = client._chat_openai_compat(
            messages=[{"role": "user", "content": "输出 JSON"}],
            tools=None,
            temperature=0.1,
            max_tokens=7000,
            response_format={"type": "json_object"},
        )

        self.assertEqual("response", response)
        self.assertEqual(
            {"thinking": {"type": "disabled"}},
            captured["extra_body"],
        )
        self.assertEqual({"type": "json_object"}, captured["response_format"])

    def test_deepseek_streaming_reports_real_progress_and_aggregates_json(self) -> None:
        captured: dict = {}

        class FakeCompletions:
            def create(self, **kwargs):
                captured.update(kwargs)
                return iter(
                    [
                        SimpleNamespace(
                            choices=[
                                SimpleNamespace(
                                    delta=SimpleNamespace(content='{"ok":'),
                                    finish_reason=None,
                                )
                            ]
                        ),
                        SimpleNamespace(
                            choices=[
                                SimpleNamespace(
                                    delta=SimpleNamespace(content="true}"),
                                    finish_reason="stop",
                                )
                            ]
                        ),
                    ]
                )

        client = object.__new__(LLMClient)
        client.provider = "deepseek"
        client.model = "deepseek-v4-flash"
        client._client = SimpleNamespace(
            chat=SimpleNamespace(completions=FakeCompletions())
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            response = client._chat_openai_compat(
                messages=[{"role": "user", "content": "输出 JSON"}],
                tools=None,
                temperature=0.1,
                max_tokens=30,
                response_format={"type": "json_object"},
                stream_progress=True,
            )

        self.assertTrue(captured["stream"])
        self.assertEqual('{"ok":true}', response.choices[0].message.content)
        self.assertEqual("stop", response.choices[0].finish_reason)
        self.assertIn("模型响应", stdout.getvalue())

    def test_mock_run_uses_expected_result_and_writes_review_gated_json(self) -> None:
        fake = FakeLLM(is_mock=True)
        runner = AgentRunner(llm=fake)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            output, output_path = runner.run_weekly(REPLAY_MANIFEST, output_dir=output_dir)
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            output_files = list(output_dir.glob("*.json"))

        self.assertEqual("mock", output.run_info.mode)
        self.assertTrue(output.executive_summary.startswith("[MOCK 输出｜仅供程序烟雾测试"))
        self.assertEqual("awaiting_human_review", output.human_review.status)
        self.assertEqual([], output.human_review.external_actions)
        self.assertEqual(3, len(output.briefs))
        self.assertEqual(0, fake.chat_calls)
        self.assertEqual([output_path], output_files)
        self.assertEqual("mock", saved["run_info"]["mode"])
        self.assertEqual("awaiting_human_review", saved["human_review"]["status"])
        self.assertEqual([], saved["human_review"]["external_actions"])
        self.assertEqual(3, len(saved["briefs"]))

    def test_weekly_tools_have_no_external_action_capability(self) -> None:
        tool_names = [tool["function"]["name"] for tool in WEEKLY_TOOLS]
        self.assertEqual(list(WEEKLY_TOOL_ORDER), tool_names)
        investigation_names = [
            tool["function"]["name"] for tool in INVESTIGATION_TOOLS
        ]
        self.assertEqual(list(INVESTIGATION_ACTION_NAMES), investigation_names)
        serialized = json.dumps(
            [*WEEKLY_TOOLS, *INVESTIGATION_TOOLS], ensure_ascii=False
        ).lower()
        for forbidden in (
            "send",
            "publish",
            "feishu",
            "budget",
            "飞书",
            "发布",
            "投放",
            "预算",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_real_mode_calls_model_with_runtime_evidence_not_mock_candidate(self) -> None:
        fake = SuccessfulRealLLM()
        runner = AgentRunner(llm=fake)

        with tempfile.TemporaryDirectory() as temporary:
            output, output_path = runner.run_weekly(
                REPLAY_MANIFEST,
                output_dir=Path(temporary) / "outputs",
            )

        planning_prompt = fake.calls[0]["messages"][1]["content"]
        generation_prompt = fake.calls[1]["messages"][1]["content"]
        self.assertEqual(2, fake.chat_calls)
        self.assertEqual("real", output.run_info.mode)
        self.assertEqual("fake-real-provider", output.run_info.provider)
        self.assertIn("src_shanghai_mxgp_2026", planning_prompt)
        self.assertIn("version_decisions", generation_prompt)
        self.assertIn("merge_records", generation_prompt)
        self.assertIn("tool_feedback", generation_prompt)
        self.assertNotIn("expected-result.json", generation_prompt)
        self.assertNotIn("[MOCK 输出", output.executive_summary)
        self.assertTrue(output_path.name.startswith("brand_radar_weekly-real-"))

    def test_real_authentication_error_propagates_without_mock_or_output(self) -> None:
        expected_error = LLMRequestError("authentication", "fake-provider", "fake-model")
        fake = FakeLLM(is_mock=False, error=expected_error)
        runner = AgentRunner(llm=fake)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            with self.assertRaises(LLMRequestError) as raised:
                runner.run_weekly(REPLAY_MANIFEST, output_dir=output_dir)
            output_files = list(output_dir.glob("*")) if output_dir.exists() else []

        self.assertIs(expected_error, raised.exception)
        self.assertEqual("authentication", raised.exception.category)
        self.assertFalse(fake.is_mock)
        self.assertEqual(1, fake.chat_calls)
        self.assertEqual([], output_files)

    def test_zhipu_business_error_code_is_classified_without_response_body(self) -> None:
        class ZhipuBusyError(Exception):
            status_code = 429
            body = {"error": {"code": "1305", "message": "provider detail must stay private"}}

        error = LLMRequestError.from_exception(
            ZhipuBusyError(),
            provider="zhipu",
            model="glm-4.7-flash",
        )

        self.assertEqual("provider_unavailable", error.category)
        self.assertEqual("1305", error.business_code)
        self.assertIn("模型当前访问量过大", str(error))
        self.assertNotIn("provider detail must stay private", str(error))

    def test_configured_key_never_turns_dependency_failure_into_mock(self) -> None:
        original = LLMClient._build_client

        def fail_to_build(_client):
            raise LLMConfigurationError("missing provider dependency")

        LLMClient._build_client = fail_to_build
        try:
            with self.assertRaisesRegex(LLMConfigurationError, "missing provider dependency"):
                LLMClient(
                    provider="zhipu",
                    model="glm-4.7-flash",
                    api_key="test-key-not-a-secret",
                    require_api=False,
                )
        finally:
            LLMClient._build_client = original


if __name__ == "__main__":
    unittest.main()
