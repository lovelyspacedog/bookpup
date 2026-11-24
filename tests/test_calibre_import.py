import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.library as library
import lib.user_paths as user_paths
from lib.calibre_import import import_parts, _pick_format

CALIBRE_FIXTURE = Path("/home/tony/temp")


class CalibreImportTest(unittest.TestCase):
    def test_pick_format_prefers_epub(self) -> None:
        self.assertEqual(_pick_format(["MOBI", "EPUB", "PDF"]), "epub")

    def test_import_fixture_smoke(self) -> None:
        p1 = CALIBRE_FIXTURE / "part-0001.calibre-data"
        p2 = CALIBRE_FIXTURE / "part-0002.calibre-data"
        if not p1.is_file() or not p2.is_file():
            self.skipTest("Calibre export fixture missing")
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        core._config = {
            "username": "book",
            "password": "test",
            "port": 18478,
            "library_quota_bytes": 8 * 1024 * 1024,
        }
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"test","port":18478,"library_quota_bytes":8388608}\n'
        )
        accounts.reload_accounts()
        user_paths.set_user("book")
        result = import_parts([p1, p2])
        self.assertGreaterEqual(result["imported"], 1)
        self.assertGreaterEqual(len(library.list_items()), 1)
        self.assertTrue(
            any("quota" in (e.get("error") or "").lower() for e in result.get("errors") or [])
        )
        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None


if __name__ == "__main__":
    unittest.main()