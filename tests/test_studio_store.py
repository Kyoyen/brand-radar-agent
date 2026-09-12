from pathlib import Path
import tempfile
import unittest
import json

from studio.store import TaskStore


class StudioPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.temporary.name))
        self.task = self.store.create(title="周末的一杯", question="如何介入出发前？")
        self.task_id = self.task["id"]

    def tearDown(self):
        self.temporary.cleanup()

    def test_model_edit_preserves_user_placement_and_decision_and_original(self):
        self.store.upsert_cards(self.task_id, [{"id": "idea-a", "kind": "idea", "title": "出发前", "body": "旧稿"}])
        self.store.patch(self.task_id, {"cards": [{"id": "idea-a", "x": 137, "y": 288, "status": "kept"}]})
        self.store.upsert_cards(self.task_id, [{"id": "idea-a", "body": "带走后继续走"}])
        reopened = TaskStore(Path(self.temporary.name)).get(self.task_id)["cards"][0]
        self.assertEqual((137, 288, "kept"), (reopened["x"], reopened["y"], reopened["status"]))
        self.assertEqual("带走后继续走", reopened["body"])
        self.assertEqual("旧稿", reopened["revisions"][0]["body"])

    def test_bad_reference_does_not_partially_save_batch(self):
        with self.assertRaises(ValueError):
            self.store.upsert_cards(self.task_id, [
                {"kind": "idea", "title": "可以试", "body": "假设"},
                {"kind": "observation", "title": "不能伪造来源", "source_ids": ["missing"]},
            ])
        self.assertEqual([], self.store.get(self.task_id)["cards"])

    def test_reopened_interruption_keeps_work_and_is_not_success(self):
        self.store.add_message(self.task_id, "user", "继续想")
        self.store.mutate(self.task_id, lambda task: task.update(status="running"))
        reopened = TaskStore(Path(self.temporary.name))
        reopened.recover_interrupted()
        task = reopened.get(self.task_id)
        self.assertEqual("stopped", task["status"])
        self.assertEqual("继续想", task["messages"][0]["content"])
        self.assertIsNotNone(task["error"])

    def test_reopened_source_retains_id_and_card_reference(self):
        first = self.store.add_source(self.task_id, {"title": "原文", "url": "https://example.com/", "text": "原文"})
        self.store.upsert_cards(self.task_id, [{"kind": "source", "title": "来源", "source_ids": [first["id"]]}])
        refreshed = self.store.add_source(self.task_id, {"title": "原文", "url": "https://example.com/", "text": "更新"})
        self.assertEqual(first["id"], refreshed["id"])
        self.assertEqual(1, len(self.store.get(self.task_id)["sources"]))
        self.assertEqual("更新", self.store.get(self.task_id)["sources"][0]["text"])

    def test_phone_creates_cards_and_edges_in_one_atomic_patch(self):
        task = self.store.patch(self.task_id, {"cards": [
            {"id": "brief", "kind": "note", "title": "口述 Brief", "body": "先讨论", "x": -50, "y": 90},
            {"id": "idea", "kind": "idea", "title": "想法", "x": 500, "y": 90},
        ], "edges": [{"id": "next", "from_id": "brief", "to_id": "idea", "label": "形成创意"}]})
        self.assertEqual((-50, 90), (task["cards"][0]["x"], task["cards"][0]["y"]))
        self.assertEqual("形成创意", task["edges"][0]["label"])
        reopened = TaskStore(Path(self.temporary.name)).get(self.task_id)
        self.assertEqual(task, reopened)
        with self.assertRaises(ValueError):
            self.store.patch(self.task_id, {"cards": [{"id": "brief", "body": "不应保存"}],
                                           "edges": [{"from_id": "brief", "to_id": "missing"}]})
        self.assertEqual(reopened, self.store.get(self.task_id))

    def test_user_card_creation_without_id_preserves_placement(self):
        task = self.store.patch(self.task_id, {"cards": [{"title": "便签", "x": 15, "y": 27, "status": "kept"}]})
        self.assertTrue(task["cards"][0]["id"])
        self.assertEqual((15, 27, "kept"), tuple(task["cards"][0][key] for key in ("x", "y", "status")))

    def test_edge_patch_is_partial_and_removal_does_not_remove_cards(self):
        self.store.patch(self.task_id, {"cards": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                                       "edges": [{"id": "ab", "from_id": "a", "to_id": "b", "label": "依据"},
                                                 {"id": "bc", "from_id": "b", "to_id": "c", "label": "行动"}]})
        task = self.store.patch(self.task_id, {"edges": [{"id": "ab", "label": "推导"}]})
        self.assertEqual(["推导", "行动"], [edge["label"] for edge in task["edges"]])
        task = self.store.patch(self.task_id, {"remove_edge_ids": ["ab"]})
        self.assertEqual(["bc"], [edge["id"] for edge in task["edges"]])
        self.assertEqual(3, len(task["cards"]))

    def test_old_task_without_edges_is_readable(self):
        del self.task["edges"]
        self.store.path(self.task_id).write_text(json.dumps(self.task), encoding="utf-8")
        self.assertEqual([], self.store.get(self.task_id)["edges"])

    def test_invalid_card_id_and_malformed_edge_do_not_save(self):
        for update in ({"cards": [{"id": "bad/id"}]}, {"cards": [None]}, {"edges": [None]}):
            with self.assertRaises(ValueError):
                self.store.patch(self.task_id, update)
        self.assertEqual([], self.store.get(self.task_id)["cards"])


if __name__ == "__main__":
    unittest.main()
