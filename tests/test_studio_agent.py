"""Behavioral checks for real-only execution, draft recovery, and public reads."""

import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from studio.agent import _execute, _load_methods, _provider_messages, _source_result, run_agent
from studio.store import TaskStore
from studio.tools import _download, _public_target, fetch_url


def response(*calls, content=""):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=[
            SimpleNamespace(id=f"call-{i}", function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))
            for i, (name, arguments) in enumerate(calls)
        ]), finish_reason="tool_calls" if calls else "stop",
    )])


class ScriptedClient:
    is_mock = False
    provider = "test-provider"
    model = "scripted-tool-responses"

    def __init__(self, *responses):
        self.responses = list(responses)

    def chat(self, **kwargs):
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class StudioAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = TaskStore(Path(self.tmp.name))
        self.task = self.store.create(title="咖啡与午后", question="提出一个可以讨论的假设")
        self.task_id = self.task["id"]
        self.store.add_message(self.task_id, "user", "提出一个可以讨论的假设")

    def test_explicit_finish_saves_the_real_tool_result(self):
        client = ScriptedClient(response(("update_board", {"cards": [{"kind": "idea", "title": "午后换个节奏", "body": "假设：可以试一个午休后的短暂散步场景。", "source_ids": []}]})), response(("finish", {"summary": "留下了一个创意假设，尚无效果证据。"})))
        with patch("studio.agent.LLMClient", return_value=client) as constructor:
            run_agent(self.task_id, self.store, threading.Event())
        constructor.assert_called_once_with(require_api=True)
        task = self.store.get(self.task_id)
        self.assertEqual(task["status"], "idle")
        self.assertEqual(len(task["cards"]), 1)
        self.assertIn("尚无效果证据", task["messages"][-1]["content"])

    def test_failure_keeps_cards_without_claiming_completion(self):
        client = ScriptedClient(response(("update_board", {"cards": [{"kind": "idea", "title": "留下草稿", "body": "可以试一个新场景。"}]})), RuntimeError("provider disconnected"))
        with patch("studio.agent.LLMClient", return_value=client):
            run_agent(self.task_id, self.store, threading.Event())
        task = self.store.get(self.task_id)
        self.assertEqual(task["status"], "error")
        self.assertEqual(task["cards"][0]["title"], "留下草稿")
        self.assertFalse(any(message["role"] == "assistant" for message in task["messages"]))

    def test_round_limit_and_stop_do_not_execute_pending_edits(self):
        with patch("studio.agent.LLMClient", return_value=ScriptedClient(response(content="正在想"))), patch("studio.agent.MAX_ROUNDS", 1):
            run_agent(self.task_id, self.store, threading.Event())
        self.assertEqual(self.store.get(self.task_id)["status"], "stopped")
        event = threading.Event()
        client = ScriptedClient()
        def canceled(**kwargs):
            event.set()
            return response(("update_board", {"cards": [{"title": "不该写入"}]}))
        client.chat = canceled
        with patch("studio.agent.LLMClient", return_value=client):
            run_agent(self.task_id, self.store, event)
        self.assertEqual(self.store.get(self.task_id)["cards"], [])

    def test_selected_edit_preserves_other_cards_and_user_decisions(self):
        self.store.upsert_cards(self.task_id, [{"id": "one", "title": "保留", "body": "原稿"}, {"id": "two", "title": "不改", "body": "旁边的稿"}])
        self.store.patch(self.task_id, {"cards": [{"id": "one", "status": "kept", "x": 800}]})
        with self.assertRaises(ValueError):
            _execute("update_board", {"cards": [{"id": "two", "body": "越界修改"}]}, self.task_id, self.store, {"one"})
        _execute("update_board", {"cards": [{"id": "one", "body": "依据反馈修改", "x": 0, "status": "draft"}]}, self.task_id, self.store, {"one"})
        one, two = self.store.get(self.task_id)["cards"]
        self.assertEqual((one["x"], one["status"]), (800, "kept"))
        self.assertEqual(two["body"], "旁边的稿")
        with self.assertRaises(ValueError):
            _execute("update_board", {"cards": [{"title": "坏引用", "source_ids": ["invented"]}]}, self.task_id, self.store, set())
        self.store.add_message(self.task_id, "user", "请整体修订这次企划，保留卡片位置与保留状态。")
        _execute("update_board", {"cards": [{"id": "one", "body": "继续推敲后的短稿"}]}, self.task_id, self.store, set())
        cards = self.store.get(self.task_id)["cards"]
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["body"], "继续推敲后的短稿")
        self.assertEqual((cards[0]["id"], cards[0]["x"], cards[0]["status"]), ("one", 800, "kept"))
        self.assertEqual(cards[0]["revisions"][-1]["body"], "依据反馈修改")

    def test_observation_needs_a_real_reference_but_ideas_can_be_hypotheses(self):
        with self.assertRaises(ValueError):
            _execute("update_board", {"cards": [{"kind": "observation", "title": "缺少支撑", "body": "人们都这样消费", "source_ids": []}]}, self.task_id, self.store, set())
        source = self.store.add_source(self.task_id, {"title": "用户材料", "text": "给出了具体事实", "origin": "manual"})
        _execute("update_board", {"cards": [{"kind": "observation", "title": "有依据的观察", "body": "材料描述了一种行为。", "source_ids": [source["id"]]}]}, self.task_id, self.store, set())
        self.assertEqual(self.store.get(self.task_id)["cards"][0]["source_ids"], [source["id"]])

    def test_anthropic_tool_history_retains_result_association(self):
        messages = [{"role": "assistant", "content": "", "tool_calls": [{"id": "abc", "function": {"name": "read_source", "arguments": '{"source_id":"s1"}'}}]}, {"role": "tool", "tool_call_id": "abc", "content": "source text"}]
        converted = _provider_messages(messages, "anthropic")
        self.assertEqual(converted[0]["content"][0]["input"], {"source_id": "s1"})
        self.assertEqual(converted[1]["content"][0]["tool_use_id"], "abc")

    def test_professional_guidance_is_reread_for_the_next_run(self):
        root = Path(self.tmp.name) / "guidance"
        (root / "agent").mkdir(parents=True)
        (root / "agent/AGENTS.md").write_text("新的运行规则", encoding="utf-8")
        for name in ("signal-triage", "brand-fit", "brief-distillation"):
            path = root / "skills/brand-radar" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"---\nname: {name}\n---\n{name} 专业正文", encoding="utf-8")
        with patch("studio.agent.ROOT", root):
            first = _load_methods()
            (root / "agent/AGENTS.md").write_text("下一轮采用修改后的规则", encoding="utf-8")
            second = _load_methods()
        self.assertIn("新的运行规则", first)
        self.assertIn("brief-distillation 专业正文", first)
        self.assertNotIn("name:", first)
        self.assertIn("下一轮采用修改后的规则", second)


class PublicReaderTests(unittest.TestCase):
    @staticmethod
    def dns(host, port, **kwargs):
        address = "127.0.0.1" if host in {"127.0.0.1", "internal.example"} else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    def test_rejects_credentials_and_any_private_dns_answer(self):
        with self.assertRaises(ValueError):
            _public_target("https://account:secret@example.com")
        with patch("studio.tools.socket.getaddrinfo", return_value=self.dns("public.example", 443) + self.dns("internal.example", 443)):
            with self.assertRaises(ValueError):
                _public_target("https://public.example")

    def test_redirect_cannot_reach_private_host_and_connection_is_pinned(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(302, headers={"location": "http://internal.example"})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch("studio.tools.httpx.Client", return_value=client), patch("studio.tools.socket.getaddrinfo", side_effect=self.dns):
            with self.assertRaises(ValueError):
                _download("https://public.example/article")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.host, "93.184.216.34")
        self.assertEqual(requests[0].headers["host"], "public.example")
        self.assertEqual(requests[0].extensions["sni_hostname"], "public.example")

    def test_reader_uses_actual_text_and_strips_executable_content(self):
        html = '<html><head><title>实际标题</title><script>steal secrets</script></head><body><p>真实材料正文。这个段落包含可以读取的事实，但不应由读取工具额外补写其他结论。它只是原文。</p></body></html>'
        with patch("studio.tools._download", return_value=(html, "https://public.example/article", "text/html")):
            source = fetch_url("https://public.example/article")
        self.assertEqual(source["title"], "实际标题")
        self.assertNotIn("steal secrets", source["text"])
        self.assertIn("它只是原文", source["text"])

    def test_truncated_page_is_not_presented_as_a_complete_read(self):
        with patch("studio.tools._download", return_value=("原文" * 20_000, "https://public.example/article", "text/plain")):
            source = fetch_url("https://public.example/article")
        self.assertTrue(source["truncated"])
        first = _source_result(source)
        last = _source_result(source, 24_000)
        self.assertEqual(first["next_offset"], 12_000)
        self.assertIn("不能当作已读全文", first["reader_note"])
        self.assertEqual(len(last["untrusted_source_text"]), 6_000)
        self.assertIsNone(last["next_offset"])


if __name__ == "__main__":
    unittest.main()
