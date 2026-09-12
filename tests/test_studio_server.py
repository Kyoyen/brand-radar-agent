"""Exercise the actual phone HTTP boundary, not just token comparison helpers."""

import json
import stat
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from studio.server import Handler, Studio, phone_pairing
from studio.store import TaskStore


class StudioPhoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.app = Studio(TaskStore(self.root))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.app = self.app
        self.server.phone_mode = True
        self.server.phone_token = "unit-test-token-which-is-not-a-secret"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.app.shutdown()
        self.tmp.cleanup()

    def request(self, method, path, body=None, token=None, **headers):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        if token:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        raw = response.read()
        status = response.status
        connection.close()
        return status, json.loads(raw) if raw else None

    def test_unpaired_requests_cannot_read_status_tasks_or_write(self):
        for method, path, body in (("GET", "/api/status", None), ("GET", "/api/tasks", None),
                                   ("POST", "/api/tasks", {"question": "不要创建"})):
            self.assertEqual(401, self.request(method, path, body)[0])
            self.assertEqual(401, self.request(method, path, body, token="wrong")[0])
        self.assertEqual([], self.app.store.list())

    def test_paired_lan_host_can_create_and_patch_connected_board(self):
        token = self.server.phone_token
        status, state = self.request("GET", "/api/status", token=token, Host="192.168.1.2")
        self.assertEqual(200, status)
        self.assertTrue(state["phone_mode"])
        self.assertNotIn("token", state)
        status, task = self.request("POST", "/api/tasks", {"question": "手机画布"}, token)
        self.assertEqual(201, status)
        status, task = self.request("PATCH", f"/api/tasks/{task['id']}", {
            "cards": [{"id": "a", "title": "想法"}, {"id": "b", "title": "下一步"}],
            "edges": [{"from_id": "a", "to_id": "b", "label": "行动"}],
        }, token)
        self.assertEqual(200, status)
        self.assertEqual("行动", task["edges"][0]["label"])

    def test_phone_rejects_browser_origins_and_local_mode_keeps_host_boundary(self):
        self.assertEqual(403, self.request("GET", "/api/status", token=self.server.phone_token,
                                           Origin="https://elsewhere.example")[0])
        self.server.phone_mode = False
        self.assertEqual(200, self.request("GET", "/api/status")[0])
        self.assertEqual(403, self.request("GET", "/api/status", Host="attacker.example")[0])

    def test_pairing_is_private_and_stable_across_restart(self):
        first = phone_pairing(self.root, 8765)
        second = phone_pairing(self.root, 8766)
        self.assertEqual(first["token"], second["token"])
        self.assertEqual(8766, second["port"])
        path = self.root / "phone-pairing.json"
        self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
        self.assertEqual(second, json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
