import json
import threading
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
from lib.server import Handler


class ServerPublicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"secret","irc_server":"h","irc_port":6667,'
            '"public_url":"https://sync.test"}'
        )
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
        self.tmp.cleanup()
        core._config = None

    def _get_json(self, path: str) -> dict:
        with urllib.request.urlopen(self.base + path, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            return json.loads(resp.read().decode())

    def test_health(self) -> None:
        body = self._get_json("/api/health")
        self.assertEqual(body.get("version"), core.VERSION)
        self.assertTrue(body.get("config_dir_writable"))
        self.assertIn("irc_worker_alive", body)
        self.assertIn("public_url_configured", body)
        self.assertTrue(body.get("public_url_configured"))

    def test_config_koreader_url(self) -> None:
        body = self._get_json("/api/config")
        self.assertEqual(body.get("koreader_sync_url"), "https://sync.test")

    def test_manifest_webmanifest(self) -> None:
        with urllib.request.urlopen(self.base + "/manifest.webmanifest", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/manifest+json", resp.headers.get("Content-Type", ""))
            body = json.loads(resp.read().decode())
        self.assertEqual(body.get("display"), "standalone")
        self.assertEqual(body.get("name"), "BookPup")
        icons = body.get("icons") or []
        self.assertTrue(any("192" in str(i.get("sizes", "")) for i in icons))
        maskable = [i for i in icons if i.get("purpose") == "maskable"]
        self.assertTrue(len(maskable) >= 2)

    def test_service_worker(self) -> None:
        with urllib.request.urlopen(self.base + "/sw.js", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            text = resp.read().decode()
        self.assertIn(core.VERSION, text)
        self.assertIn("reader.js", text)
        self.assertEqual(resp.headers.get("Service-Worker-Allowed"), "/")

    def test_head_manifest_and_sw(self) -> None:
        for path in ("/manifest.webmanifest", "/sw.js"):
            req = urllib.request.Request(self.base + path, method="HEAD")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertGreater(int(resp.headers.get("Content-Length", "0")), 0)
                self.assertEqual(resp.read(), b"")

if __name__ == "__main__":
    unittest.main()