"""Automated API smoke (mock IRC). Maps to RELEASE-1.0.0.md matrix rows 1, 7 (partial)."""

import json
import os
import threading
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import urllib.error
import urllib.request

os.environ["BOOKPUP_IRC_MOCK"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.auth as auth
import lib.core as core
from lib.server import Handler


class SmokeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        core.SESSIONS_FILE = core.CONFIG_DIR / "sessions.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"secret","irc_server":"h","irc_port":6667,'
            '"public_url":"https://smoke.example.test"}'
        )
        core._config = None
        core.IRC_MOCK = True
        auth._sessions.clear()
        Handler.config = core.load_config()
        from lib.irc_worker import worker

        worker.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.http_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.http_thread.start()
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        auth._sessions.clear()
        self.tmp.cleanup()
        core._config = None

    def _request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        hdrs = {"Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(self.base + path, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode()
            try:
                return exc.code, json.loads(payload)
            except json.JSONDecodeError:
                return exc.code, {"error": payload}

    def test_login_session_logout_wrong_password(self) -> None:
        code, body = self._request(
            "POST",
            "/api/login",
            {"username": "book", "password": "wrong"},
        )
        self.assertEqual(code, 401)
        code, body = self._request(
            "POST",
            "/api/login",
            {"username": "book", "password": "secret"},
        )
        self.assertEqual(code, 200)
        token = body["token"]
        code, sess = self._request(
            "GET",
            "/api/session",
            headers={"Authorization": f"Bearer {token}", "X-Bookpup": "1"},
        )
        self.assertEqual(code, 200)
        self.assertEqual(sess.get("username"), "book")
        code, _ = self._request(
            "POST",
            "/api/logout",
            headers={"Authorization": f"Bearer {token}", "X-Bookpup": "1"},
        )
        self.assertEqual(code, 200)
        code, _ = self._request(
            "GET",
            "/api/session",
            headers={"Authorization": f"Bearer {token}", "X-Bookpup": "1"},
        )
        self.assertEqual(code, 401)

    def test_config_public_url(self) -> None:
        code, body = self._request("GET", "/api/config")
        self.assertEqual(code, 200)
        self.assertEqual(body.get("koreader_sync_url"), "https://smoke.example.test")

    def test_fresh_upload_session_create(self) -> None:
        _, login = self._request(
            "POST",
            "/api/login",
            {"username": "book", "password": "secret"},
        )
        token = login["token"]
        headers = {"Authorization": f"Bearer {token}", "X-Bookpup": "1"}
        code, body = self._request(
            "POST",
            "/api/library/upload/session",
            {"parts": [{"name": "smoke.txt", "size": 4}]},
            headers=headers,
        )
        self.assertEqual(code, 201)
        self.assertTrue(body.get("session_id"))
        self.assertEqual(body.get("chunk_size"), 4 * 1024 * 1024)

    def test_search_saved_list(self) -> None:
        _, login = self._request(
            "POST",
            "/api/login",
            {"username": "book", "password": "secret"},
        )
        token = login["token"]
        headers = {"Authorization": f"Bearer {token}", "X-Bookpup": "1"}
        code, body = self._request("GET", "/api/search/saved", headers=headers)
        self.assertEqual(code, 200)
        self.assertIsInstance(body.get("saved"), list)

    def test_search_queues_mock_job(self) -> None:
        _, login = self._request(
            "POST",
            "/api/login",
            {"username": "book", "password": "secret"},
        )
        token = login["token"]
        headers = {"Authorization": f"Bearer {token}", "X-Bookpup": "1"}
        code, job = self._request(
            "POST",
            "/api/search",
            {"query": "test author", "channel": "irchighway:ebooks"},
            headers=headers,
        )
        self.assertIn(code, (200, 201))
        job_id = job.get("id") or (job.get("job") or {}).get("id")
        self.assertTrue(job_id)


if __name__ == "__main__":
    unittest.main()