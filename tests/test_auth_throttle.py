import base64
import json
import threading
import tempfile
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.login_limit as login_limit
from lib.login_limit import MAX_FAILURES, bootstrap_failures, record_success
from lib.server import Handler


class AuthThrottleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            json.dumps({"username": "book", "password": "secret", "port": 18478})
        )
        accounts.reload_accounts()
        login_limit._FAILURES_FILE = core.CONFIG_DIR / "login_throttle.json"
        login_limit._loaded = False
        login_limit._failures.clear()
        bootstrap_failures()
        core._config = None
        Handler.config = core.load_config()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.http_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.http_thread.start()
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        record_success("127.0.0.1")
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def test_opds_blocks_after_failed_auth_burst(self) -> None:
        bad = base64.b64encode(b"book:wrong").decode()
        for _ in range(MAX_FAILURES):
            req = urllib.request.Request(
                self.base + "/opds/catalog",
                headers={"Authorization": f"Basic {bad}"},
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(ctx.exception.code, 401)
        req = urllib.request.Request(
            self.base + "/opds/catalog",
            headers={"Authorization": f"Basic {bad}"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 429)


if __name__ == "__main__":
    unittest.main()