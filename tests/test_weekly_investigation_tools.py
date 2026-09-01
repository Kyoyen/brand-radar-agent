from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import scenarios.brand_radar_weekly as weekly
from scenarios.brand_radar_weekly import WEEKLY_TOOL_ORDER, WeeklyScenarioRuntime


def _material(
    source_id: str,
    *,
    title: str,
    event_key: str,
    version_group: str,
    version_rank: int,
    brands: list[str],
    verification_status: str = "verified",
    supersedes: list[str] | None = None,
    duplicate_of: str | None = None,
    valid_to: str = "2026-09-30",
) -> dict:
    return {
        "source_id": source_id,
        "title": title,
        "source_type": "REPLAY",
        "source_date": "2026-09-01",
        "url": None,
        "file": f"sources/{source_id}.md",
        "event_key": event_key,
        "version_group": version_group,
        "version_rank": version_rank,
        "supersedes": supersedes or [],
        "duplicate_of": duplicate_of,
        "valid_from": "2026-09-01",
        "valid_to": valid_to,
        "verification_status": verification_status,
        "brands": brands,
        "regions": ["全国"],
    }


def _manifest() -> dict:
    return {
        "schema_version": "1.0",
        "pack_id": "weekly-investigation-test-pack",
        "pack_mode": "REPLAY",
        "settings": {
            "brand": "瑞幸咖啡",
            "category": "现制咖啡",
            "regions": ["全国"],
            "competitors": ["星巴克中国", "库迪咖啡"],
            "keywords": ["社区空间", "教师节"],
            "business_question": "下周哪些营销信号值得进入企划会？",
            "observation_window": {"start": "2026-09-07", "end": "2026-09-13"},
            "calendar_window": {"start": "2026-09-07", "end": "2026-10-06"},
            "safety_boundaries": ["默认停在人工复核前"],
            "review_deadline": "2026-09-04",
        },
        "materials": [
            _material(
                "source-old",
                title="品牌活动旧版",
                event_key="brand-campaign",
                version_group="brand-campaign-versions",
                version_rank=1,
                brands=["瑞幸咖啡"],
            ),
            _material(
                "source-current",
                title="品牌活动当前版",
                event_key="brand-campaign",
                version_group="brand-campaign-versions",
                version_rank=2,
                supersedes=["source-old"],
                brands=["瑞幸咖啡"],
            ),
            _material(
                "source-competitor",
                title="星巴克社区空间动作",
                event_key="competitor-community",
                version_group="competitor-community-versions",
                version_rank=1,
                brands=["星巴克中国"],
            ),
            _material(
                "source-competitor-note",
                title="星巴克社区空间待核补充",
                event_key="competitor-community",
                version_group="competitor-community-versions",
                version_rank=1,
                brands=["星巴克中国"],
                verification_status="unverified",
                duplicate_of="source-competitor",
            ),
            _material(
                "source-conflict-a",
                title="同级版本 A",
                event_key="conflicting-event",
                version_group="conflicting-versions",
                version_rank=3,
                brands=["瑞幸咖啡"],
            ),
            _material(
                "source-conflict-b",
                title="同级版本 B",
                event_key="conflicting-event",
                version_group="conflicting-versions",
                version_rank=3,
                brands=["瑞幸咖啡"],
            ),
        ],
    }


def _write_pack(root: Path, manifest: dict | None = None) -> Path:
    manifest = manifest or _manifest()
    for material in manifest["materials"]:
        source_path = root / material["file"]
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            f"# {material['title']}\n\n{material['source_id']} 的本地 Replay 证据。",
            encoding="utf-8",
        )
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def _completed_runtime(root: Path, manifest: dict | None = None) -> WeeklyScenarioRuntime:
    runtime = WeeklyScenarioRuntime(_write_pack(root, manifest))
    for tool_name in WEEKLY_TOOL_ORDER:
        result = json.loads(runtime.execute(tool_name, {}))
        if "error" in result:
            raise AssertionError(result["error"])
    return runtime


class WeeklyEvidenceConservatismTests(unittest.TestCase):
    def test_expired_higher_rank_does_not_hide_current_lower_rank(self) -> None:
        manifest = _manifest()
        manifest["materials"].extend(
            [
                _material(
                    "source-still-current",
                    title="仍在有效期内的基础版",
                    event_key="expiry-fallback-event",
                    version_group="expiry-fallback-versions",
                    version_rank=1,
                    brands=["瑞幸咖啡"],
                ),
                _material(
                    "source-higher-expired",
                    title="已过期的高版本",
                    event_key="expiry-fallback-event",
                    version_group="expiry-fallback-versions",
                    version_rank=2,
                    brands=["瑞幸咖啡"],
                    valid_to="2026-09-06",
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary), manifest)

        payload = runtime.validator_payload()
        decisions = {item["source_id"]: item for item in payload["version_decisions"]}
        self.assertEqual("current", decisions["source-still-current"]["status"])
        self.assertEqual("expired", decisions["source-higher-expired"]["status"])

        event = next(
            item
            for item in payload["merge_records"]
            if item["event_key"] == "expiry-fallback-event"
        )
        self.assertEqual(["source-still-current"], event["source_ids"])
        self.assertEqual("source-still-current", event["primary_source_id"])

    def test_tied_highest_versions_without_explicit_relation_stay_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary))

        decisions = {
            item["source_id"]: item
            for item in runtime.validator_payload()["version_decisions"]
        }
        self.assertEqual("unresolved_conflict", decisions["source-conflict-a"]["status"])
        self.assertEqual("source-conflict-a", decisions["source-conflict-a"]["effective_source_id"])
        self.assertEqual("unresolved_conflict", decisions["source-conflict-b"]["status"])
        self.assertEqual("source-conflict-b", decisions["source-conflict-b"]["effective_source_id"])

        events = {
            item["event_key"]: item
            for item in runtime.validator_payload()["merge_records"]
        }
        self.assertIn("conflicting-event", events)
        self.assertEqual("unverified", events["conflicting-event"]["verification_status"])

    def test_only_tied_highest_candidates_are_unresolved_and_merged(self) -> None:
        manifest = _manifest()
        manifest["materials"].extend(
            [
                _material(
                    "source-conflict-old",
                    title="同组仍有效旧版",
                    event_key="conflicting-event",
                    version_group="conflicting-versions",
                    version_rank=2,
                    brands=["瑞幸咖啡"],
                ),
                _material(
                    "source-conflict-expired",
                    title="同组已过期旧版",
                    event_key="conflicting-event",
                    version_group="conflicting-versions",
                    version_rank=1,
                    brands=["瑞幸咖啡"],
                    valid_to="2026-09-06",
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary), manifest)

        payload = runtime.validator_payload()
        decisions = {item["source_id"]: item for item in payload["version_decisions"]}
        self.assertEqual("unresolved_conflict", decisions["source-conflict-a"]["status"])
        self.assertEqual("unresolved_conflict", decisions["source-conflict-b"]["status"])
        self.assertEqual("superseded", decisions["source-conflict-old"]["status"])
        self.assertEqual("superseded", decisions["source-conflict-expired"]["status"])

        event = next(
            item
            for item in payload["merge_records"]
            if item["event_key"] == "conflicting-event"
        )
        self.assertEqual(
            ["source-conflict-a", "source-conflict-b"],
            event["source_ids"],
        )
        self.assertEqual(2, event["material_count"])
        self.assertIn(
            event["primary_source_id"],
            {"source-conflict-a", "source-conflict-b"},
        )

    def test_any_unverified_source_keeps_merged_event_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary))

        events = {
            item["event_key"]: item
            for item in runtime.validator_payload()["merge_records"]
        }
        self.assertEqual("unverified", events["competitor-community"]["verification_status"])


class WeeklyInvestigationRuntimeTests(unittest.TestCase):
    def test_observation_payload_is_a_lightweight_pack_bound_planning_view(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary))
            method = getattr(runtime, "observation_payload", None)
            self.assertIsNotNone(method, "WeeklyScenarioRuntime must expose observation_payload()")
            payload = method()

        self.assertEqual(
            "下周哪些营销信号值得进入企划会？",
            payload["marketing_goal"]["business_question"],
        )
        self.assertEqual(
            {
                "source-current",
                "source-old",
                "source-competitor",
                "source-competitor-note",
                "source-conflict-a",
                "source-conflict-b",
            },
            {item["source_id"] for item in payload["evidence_index"]},
        )
        self.assertEqual(
            ["conflicting-versions"],
            payload["attention_required"]["unresolved_version_groups"],
        )
        self.assertEqual(
            ["source-competitor-note"],
            payload["attention_required"]["unverified_source_ids"],
        )
        self.assertEqual(
            ["库迪咖啡"],
            payload["attention_required"]["competitors_without_evidence"],
        )
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("本地 Replay 证据", serialized)
        self.assertNotIn("sources/", serialized)
        self.assertNotIn("http://", serialized)
        self.assertNotIn("https://", serialized)

    def test_investigation_tool_schemas_allow_only_pack_reference_arguments(self) -> None:
        tools = getattr(weekly, "INVESTIGATION_TOOLS", None)
        self.assertIsNotNone(tools, "weekly scenario must expose INVESTIGATION_TOOLS")
        contracts = {
            item["function"]["name"]: item["function"]["parameters"]
            for item in tools
        }
        self.assertEqual(
            {
                "inspect_local_evidence": "source_id",
                "compare_event_versions": "version_group",
                "compare_competitor_evidence": "competitor",
                "cross_check_conflicting_evidence": "event_key",
            },
            {
                name: next(iter(schema["properties"]))
                for name, schema in contracts.items()
            },
        )
        for name, schema in contracts.items():
            with self.subTest(action=name):
                field = next(iter(schema["properties"]))
                self.assertEqual([field], schema["required"])
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual("string", schema["properties"][field]["type"])

        serialized = json.dumps(tools, ensure_ascii=False).lower()
        for forbidden in ("path", "file", "url", "shell", "network", "write", "路径", "联网", "写入"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_three_distinct_actions_return_traceable_business_feedback_then_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary))
            method = getattr(runtime, "execute_investigation_action", None)
            self.assertIsNotNone(
                method,
                "WeeklyScenarioRuntime must expose execute_investigation_action()",
            )
            results = [
                method("inspect_local_evidence", {"source_id": "source-current"}),
                method(
                    "compare_event_versions",
                    {"version_group": "brand-campaign-versions"},
                ),
                method(
                    "compare_competitor_evidence",
                    {"competitor": "星巴克中国"},
                ),
            ]
            with self.assertRaisesRegex(weekly.WeeklyPipelineError, "最多.*3"):
                method(
                    "cross_check_conflicting_evidence",
                    {"event_key": "conflicting-event"},
                )

        self.assertEqual(
            [
                "verified_evidence",
                "latest_version_resolved",
                "mixed_verification",
            ],
            [item["outcome"] for item in results],
        )
        self.assertEqual(
            ["source-old", "source-current"],
            results[1]["source_ids"],
        )
        self.assertEqual(
            ["source-competitor", "source-competitor-note"],
            results[2]["source_ids"],
        )
        self.assertIn("本地 Replay 证据", results[2]["summary"])
        for result in results:
            self.assertEqual(
                {"action", "arguments", "source_ids", "summary", "outcome", "decision_hint"},
                set(result),
            )
            self.assertTrue(result["summary"].strip())
            self.assertTrue(result["decision_hint"].strip())

    def test_duplicate_signature_and_out_of_pack_arguments_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary))
            method = getattr(runtime, "execute_investigation_action", None)
            self.assertIsNotNone(method)
            method("inspect_local_evidence", {"source_id": "source-current"})
            with self.assertRaisesRegex(weekly.WeeklyPipelineError, "重复"):
                method("inspect_local_evidence", {"source_id": "source-current"})
            with self.assertRaisesRegex(weekly.WeeklyPipelineError, "只接受参数"):
                method(
                    "inspect_local_evidence",
                    {"source_id": "source-old", "url": "https://example.com"},
                )
            with self.assertRaisesRegex(weekly.WeeklyPipelineError, "不在当前观察包"):
                method("inspect_local_evidence", {"source_id": "../../secret"})
            with self.assertRaisesRegex(weekly.WeeklyPipelineError, "不在当前观察包"):
                method("compare_competitor_evidence", {"competitor": "虚构竞品"})
            with self.assertRaisesRegex(weekly.WeeklyPipelineError, "不在调查白名单"):
                method("fetch_url", {"url": "https://example.com"})

    def test_competitor_without_pack_evidence_is_reported_without_invention(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary))
            method = getattr(runtime, "execute_investigation_action", None)
            self.assertIsNotNone(method)
            result = method(
                "compare_competitor_evidence",
                {"competitor": "库迪咖啡"},
            )

        self.assertEqual([], result["source_ids"])
        self.assertEqual("no_pack_evidence", result["outcome"])
        self.assertIn("库迪咖啡", result["summary"])

    def test_competitor_with_only_expired_evidence_is_not_reported_as_current(self) -> None:
        manifest = _manifest()
        manifest["materials"].append(
            _material(
                "source-cotti-expired",
                title="库迪咖啡过期旧动作",
                event_key="cotti-expired-event",
                version_group="cotti-expired-versions",
                version_rank=1,
                brands=["库迪咖啡"],
                valid_to="2026-09-06",
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary), manifest)
            observation = runtime.observation_payload()
            result = runtime.execute_investigation_action(
                "compare_competitor_evidence",
                {"competitor": "库迪咖啡"},
            )

        self.assertIn(
            "库迪咖啡",
            observation["attention_required"]["competitors_without_evidence"],
        )
        self.assertEqual(["source-cotti-expired"], result["source_ids"])
        self.assertEqual("no_current_pack_evidence", result["outcome"])
        self.assertIn("不能作为当前竞品动作", result["decision_hint"])

    def test_generation_payload_attaches_trace_to_complete_evidence(self) -> None:
        trace = {
            "plan": ["先核对品牌活动版本，再比较竞品证据"],
            "actions": [{"action": "compare_event_versions", "outcome": "latest_version_resolved"}],
            "adjustment_reason": "当前版已明确，竞品待核补充不能提升为确定事实。",
        }
        with tempfile.TemporaryDirectory() as temporary:
            runtime = _completed_runtime(Path(temporary))
            method = getattr(runtime, "generation_payload", None)
            self.assertIsNotNone(method, "WeeklyScenarioRuntime must expose generation_payload(trace)")
            payload = method(trace)

        self.assertEqual(trace, payload["investigation_trace"])
        self.assertIn("materials", payload)
        self.assertIn("version_decisions", payload)
        self.assertIn("merge_records", payload)
        self.assertIn("本地 Replay 证据", json.dumps(payload["materials"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
