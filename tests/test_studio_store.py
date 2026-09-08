from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
