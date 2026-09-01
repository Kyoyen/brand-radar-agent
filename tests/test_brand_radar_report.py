from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from framework.brand_radar_report import render_weekly_report


class BrandRadarReportTests(unittest.TestCase):
    def test_report_turns_one_result_into_a_safe_meeting_view(self) -> None:
        result = {
            "schema_version": "1.1",
            "observation_settings": {
                "brand": "瑞幸咖啡",
                "category": "现制咖啡",
                "regions": ["全国", "上海"],
                "calendar_window": {"start": "2026-09-07", "end": "2026-10-06"},
            },
            "run_info": {
                "mode": "real",
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "completed_at": "2026-09-01T00:00:00+08:00",
            },
            "executive_summary": "本周先看教师节 <script>alert(1)</script>",
            "source_catalog": [
                {
                    "source_id": "source-1",
                    "title": "教育部通知",
                    "url": "https://example.com/source",
                    "verification_status": "verified",
                }
            ],
            "intelligence_cards": [
                {
                    "card_id": "card-1",
                    "title": "教师节节点",
                    "fact_summary": "9 月 10 日是教师节。",
                    "event_date": "2026-09-10",
                    "regions": ["全国"],
                    "priority": "follow_up_this_week",
                    "why_it_matters": "观察周内的明确节点。",
                    "recommendation": "进入企划会讨论。",
                    "pending_questions": ["品牌表达是否合适？"],
                    "source_ids": ["source-1"],
                },
                {
                    "card_id": "card-risk",
                    "title": "主动避开的风险",
                    "fact_summary": "这条信息尚未核实。",
                    "event_date": "2026-09-11",
                    "regions": ["全国"],
                    "priority": "actively_avoid",
                    "why_it_matters": "未经核实不能进入对外计划。",
                    "recommendation": "先避开并交给人确认。",
                    "pending_questions": ["是否已有公开确认？"],
                    "source_ids": ["source-1"],
                },
            ],
            "calendar": [
                {"date": "2026-09-10", "title": "教师节", "kind": "节日节点"}
            ],
            "keywords": [{"keyword": "教师节"}],
            "briefs": [
                {
                    "perspective": "timing_window",
                    "angle": "教师节限时表达",
                    "why_now": "节点就在本周。",
                    "audience_or_scenario": "教师群体",
                    "card_ids": ["card-1"],
                    "next_step": "先完成品牌语气复核。",
                    "missing_evidence": ["活动机制"],
                    "risk_note": "避免过度商业化。",
                }
            ],
            "investigation_trace": {
                "goal_snapshot": {"business_question": "本周哪些节点值得讨论？"},
                "plan_steps": [{"step_id": "step-1", "objective": "核对教师节"}],
                "selected_actions": [
                    {
                        "action_id": "action-1",
                        "step_id": "step-1",
                        "reason": "节点直接影响本周排期。",
                    }
                ],
                "tool_feedback": [
                    {
                        "action_id": "action-1",
                        "outcome": "latest_version_resolved",
                        "summary": "已确认当前通知。",
                    }
                ],
                "adjustment_reasons": [
                    {"action_id": "action-1", "reason": "因此保留教师节节点。"}
                ],
            },
            "human_review": {
                "items": [{"question": "教师节表达是否符合品牌语气？"}]
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "weekly.json"
            json_path.write_text("{}", encoding="utf-8")
            report_path = render_weekly_report(result, json_path=json_path)
            content = report_path.read_text(encoding="utf-8")

            self.assertEqual(report_path, root / "weekly.html")
            self.assertIn("这周先讨论什么", content)
            self.assertIn("三条企划 Brief", content)
            self.assertIn("Agent 为什么查这些", content)
            self.assertIn("https://example.com/source", content)
            self.assertIn("等你确认后再使用", content)
            self.assertIn("本周优先讨论：教师节节点", content)
            self.assertIn("明确不采用：主动避开的风险", content)
            self.assertLess(
                content.index("主动避开的风险"),
                content.index("三条企划 Brief"),
            )
            self.assertNotIn("<script>alert(1)</script>", content)
            self.assertFalse(report_path.with_suffix(".html.tmp").exists())

    def test_needs_verification_stays_above_briefs_when_follow_up_is_crowded(self) -> None:
        cards = []
        for index in range(4):
            cards.append(
                {
                    "card_id": f"card-follow-{index}",
                    "title": f"本周跟进信号 {index}",
                    "fact_summary": "这是一条本周可讨论信号。",
                    "event_date": f"2026-09-1{index}",
                    "regions": ["上海"],
                    "priority": "follow_up_this_week",
                    "why_it_matters": "观察周内需要讨论。",
                    "recommendation": "进入企划会。",
                    "pending_questions": [],
                    "source_ids": ["source-1"],
                }
            )
        cards.append(
            {
                "card_id": "card-popup-needs-verification",
                "title": "上海咖啡快闪待核",
                "fact_summary": "只有人工便签，缺少主办方和地址。",
                "event_date": "2026-09-12",
                "regions": ["上海"],
                "priority": "needs_verification",
                "why_it_matters": "品类和日期相关，但证据不足。",
                "recommendation": "先补证，不能写成确定事实。",
                "pending_questions": ["主办方是谁？", "是否有公开页面？"],
                "source_ids": ["source-1"],
            }
        )
        result = {
            "schema_version": "1.1",
            "observation_settings": {
                "brand": "瑞幸咖啡",
                "category": "现制咖啡",
                "regions": ["上海"],
                "calendar_window": {"start": "2026-09-07", "end": "2026-10-06"},
            },
            "run_info": {"mode": "real", "provider": "deepseek", "model": "deepseek-v4-flash"},
            "executive_summary": "本周应主动避开未核验的上海咖啡快闪。",
            "source_catalog": [
                {
                    "source_id": "source-1",
                    "title": "测试来源",
                    "url": "https://example.com/source",
                    "verification_status": "verified",
                }
            ],
            "intelligence_cards": cards,
            "calendar": [],
            "keywords": [],
            "briefs": [
                {
                    "perspective": "risk_control",
                    "angle": "待核快闪先补证",
                    "why_now": "时间在观察周内。",
                    "audience_or_scenario": "上海咖啡用户",
                    "card_ids": ["card-popup-needs-verification"],
                    "next_step": "补主办方和公开页面。",
                    "missing_evidence": ["主办方", "地址", "公开页面"],
                    "risk_note": "不能把便签写成事实。",
                }
            ],
            "investigation_trace": None,
            "human_review": {"items": [{"question": "快闪是否有公开来源？"}]},
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "weekly.json"
            json_path.write_text("{}", encoding="utf-8")
            content = render_weekly_report(result, json_path=json_path).read_text(
                encoding="utf-8"
            )

        self.assertLess(
            content.index("上海咖啡快闪信息不完整"),
            content.index("三条企划 Brief"),
        )
        self.assertLess(
            content.index("<h3>上海咖啡快闪信息不完整</h3>"),
            content.index("<h3>本周跟进信号 0</h3>"),
        )
        self.assertNotIn("待核", content)
        self.assertIn("信息还不够，先别放进方案：上海咖啡快闪", content)
        self.assertIn("先找到能确认它的公开信息再决定", content)
        self.assertNotIn("本周应主动避开尚未确认的上海咖啡快闪", content)


if __name__ == "__main__":
    unittest.main()
