"""Walk the Trail tutorial fetch API."""

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import urllib.error
import urllib.request

os.environ["BOOKPUP_IRC_MOCK"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.auth as auth
import lib.core as core
import lib.library as library
from lib.server import Handler


class WalkTrailTests(unittest.TestCase):
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

    def test_walk_trail_fetch_requires_auth(self) -> None:
        code, _ = self._request("POST", "/api/walk-trail/fetch", {"query": "Ocean"})
        self.assertEqual(code, 401)

    def test_walk_trail_fetch_stashes_mobi(self) -> None:
        _, login = self._request(
            "POST",
            "/api/login",
            {"username": "book", "password": "secret"},
        )
        token = login["token"]
        headers = {"Authorization": f"Bearer {token}", "X-Bookpup": "1"}
        code, body = self._request(
            "POST",
            "/api/walk-trail/fetch",
            {"query": "Practice Novel", "title": "Practice Novel.mobi"},
            headers=headers,
        )
        self.assertEqual(code, 200)
        self.assertTrue(body.get("library_item_id"))
        self.assertIn("mobi", str(body.get("title") or "").lower())
        code, lib = self._request("GET", "/api/library", headers=headers)
        self.assertEqual(code, 200)
        items = lib.get("items") or []
        ids = {it.get("id") for it in items}
        self.assertIn(body["library_item_id"], ids)

    def test_walk_trail_fetch_reuses_fixture_copy(self) -> None:
        _, login = self._request(
            "POST",
            "/api/login",
            {"username": "book", "password": "secret"},
        )
        token = login["token"]
        headers = {"Authorization": f"Bearer {token}", "X-Bookpup": "1"}
        code, first = self._request(
            "POST",
            "/api/walk-trail/fetch",
            {"query": "Alpha", "title": "Alpha.mobi"},
            headers=headers,
        )
        self.assertEqual(code, 200)
        code, second = self._request(
            "POST",
            "/api/walk-trail/fetch",
            {"query": "Beta", "title": "Beta.mobi"},
            headers=headers,
        )
        self.assertEqual(code, 200)
        self.assertEqual(first.get("library_item_id"), second.get("library_item_id"))

    def test_toss_practice_mobi_does_not_restash(self) -> None:
        _, login = self._request(
            "POST",
            "/api/login",
            {"username": "book", "password": "secret"},
        )
        token = login["token"]
        headers = {"Authorization": f"Bearer {token}", "X-Bookpup": "1"}
        code, body = self._request(
            "POST",
            "/api/walk-trail/fetch",
            {"query": "Ocean", "title": "Ocean.mobi"},
            headers=headers,
        )
        self.assertEqual(code, 200)
        item_id = body["library_item_id"]
        code, _ = self._request("DELETE", "/api/library/" + item_id, headers=headers)
        self.assertEqual(code, 200)
        code, lib = self._request("GET", "/api/library", headers=headers)
        self.assertEqual(code, 200)
        staged = [it for it in (lib.get("items") or []) if str(it.get("source") or "") == "download"]
        self.assertEqual(staged, [])
        import lib.user_paths as user_paths

        user_paths.set_user("book")
        job = library.auto_stash_from_job(
            {
                "id": body["job_id"],
                "type": "download",
                "state": "done",
                "staging_id": body["staging_id"],
                "raw_bytes": 1,
                "owner": "book",
            }
        )
        self.assertIsNone(job)

    def test_walk_trail_complete_records_account(self) -> None:
        _, login = self._request(
            "POST",
            "/api/login",
            {"username": "book", "password": "secret"},
        )
        token = login["token"]
        headers = {"Authorization": f"Bearer {token}", "X-Bookpup": "1"}
        code, body = self._request("POST", "/api/walk-trail/complete", {}, headers=headers)
        self.assertEqual(code, 200)
        self.assertTrue(body.get("walk_trail_completed_at"))
        code, session = self._request("GET", "/api/session", headers=headers)
        self.assertEqual(code, 200)
        self.assertTrue(session.get("walk_trail_complete"))


if __name__ == "__main__":
    unittest.main()