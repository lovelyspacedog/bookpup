import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.user_paths as user_paths


class MigrateLegacyIndexTest(unittest.TestCase):
    def test_migrate_moves_index_when_user_index_empty(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            json.dumps({"username": "admin", "password": "pw", "port": 18478})
        )
        legacy_idx = core.CONFIG_DIR / "library.json"
        legacy_idx.write_text(
            json.dumps({"items": [{"id": "x", "title": "Book", "filename": "x.epub"}]})
        )
        user_paths.ensure_user_dirs("admin")
        accounts.reload_accounts()
        idx = user_paths.library_index("admin")
        self.assertTrue(idx.is_file())
        data = json.loads(idx.read_text())
        self.assertEqual(len(data.get("items") or []), 1)
        self.assertFalse(legacy_idx.is_file())
        accounts._cache = None
        self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()