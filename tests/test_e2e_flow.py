"""Minimal E2E flows (mock IRC): login, sniff, kennel — HTTP layer for CI."""

import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import urllib.error
import urllib.request

os.environ["BOOKPUP_IRC_MOCK"] = "1"
os.environ["BOOKPUP_XDCC_MOCK"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.auth as auth
import lib.core as core
from lib.server import Handler

CSRF = {"X-Bookpup": "1"}


class E2EFlowTests(unittest.TestCase):
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
            '{"username":"book","password":"secret","irc_server":"h","irc_port":6667}'
        )
        core._config = None
        core.IRC_MOCK = True
        auth._sessions.clear()
        Handler.config = core.load_config()
        from lib.irc_worker import worker

        worker.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        auth._sessions.clear()
        self.tmp.cleanup()
        core._config = None

    def _request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        hdrs = {**CSRF, **(headers or {})}
        if data is not None:
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode()
            try:
                return exc.code, json.loads(payload)
            except json.JSONDecodeError:
                return exc.code, {"error": payload}

    def _login(self) -> dict:
        _, body = self._request("POST", "/api/login", {"username": "book", "password": "secret"})
        token = body["token"]
        return {"Authorization": f"Bearer {token}", **CSRF}

    def test_flow_login_sniff_kennel(self) -> None:
        code, health = self._request("GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(health.get("ok"))
        self.assertEqual(health.get("ok"), health.get("config_dir_writable"))

        code, ready = self._request("GET", "/api/ready")
        self.assertEqual(code, 200)
        self.assertIn("ready", ready)

        auth_hdr = self._login()
        code, search = self._request(
            "POST",
            "/api/search",
            {"query": "pillar e smoke", "channel": "irchighway:ebooks"},
            headers=auth_hdr,
        )
        self.assertIn(code, (200, 201))
        self.assertTrue(search.get("id") or (search.get("job") or {}).get("id"))

        code, lib = self._request("GET", "/api/library", headers=auth_hdr)
        self.assertEqual(code, 200)
        self.assertIn("items", lib)

    def test_spa_shell_served(self) -> None:
        with urllib.request.urlopen(self.base + "/", timeout=10) as resp:
            html = resp.read().decode()
        self.assertIn("bookpup", html.lower())
        self.assertIn("app-core.js", html)

    def test_login_gate(self) -> None:
        code, _ = self._request("GET", "/api/library")
        self.assertEqual(code, 401)