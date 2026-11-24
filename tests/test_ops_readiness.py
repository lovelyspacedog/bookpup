"""Readiness endpoint."""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
from lib.server import Handler


class ReadyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"secret","irc_server":"h","irc_port":6667}'
        )
        core._config = None
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
        self.tmp.cleanup()
        core._config = None

    def test_ready_shape(self) -> None:
        with urllib.request.urlopen(self.base + "/api/ready", timeout=10) as resp:
            body = json.loads(resp.read().decode())
        self.assertIn("ready", body)
        self.assertIn("tools", body)
        self.assertIn("calibre", body["tools"])
        self.assertTrue(body.get("config_dir_writable"))
        self.assertIsInstance(body.get("reasons"), list)