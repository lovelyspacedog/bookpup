import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.library as library
import lib.shelves as shelves
import lib.user_paths as user_paths


class ShelvesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            json.dumps(
                {
                    "username": "alice",
                    "password": "pw",
                    "port": 18478,
                    "library_quota_bytes": 10_000_000,
                }
            )
        )
        accounts.reload_accounts()
        user_paths.set_user("alice")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def test_create_assign_and_rename(self) -> None:
        a = library.add_bytes("A", b"x" * 100, "epub", source="calibre_import")
        b = library.add_bytes("B", b"y" * 100, "epub", source="calibre_import")
        shelf = shelves.create_shelf("Beach reads")
        updated = shelves.set_shelf_items(shelf["id"], [a["id"], b["id"]])
        self.assertEqual(updated["count"], 2)
        renamed = shelves.rename_shelf(shelf["id"], "Winter stack")
        self.assertEqual(renamed["name"], "Winter stack")

    def test_delete_item_prunes_shelf(self) -> None:
        row = library.add_bytes("Gone", b"z" * 100, "epub", source="calibre_import")
        shelf = shelves.create_shelf("Tmp")
        shelves.set_shelf_items(shelf["id"], [row["id"]])
        library.delete_item(row["id"])
        listed = shelves.list_shelves()
        self.assertEqual(listed[0]["item_ids"], [])

    def test_rejects_staged_item(self) -> None:
        staged = library.add_bytes("Fresh", b"f" * 100, "epub", source="download")
        shelf = shelves.create_shelf("Nope")
        with self.assertRaises(ValueError):
            shelves.set_shelf_items(shelf["id"], [staged["id"]])

    def test_delete_shelf(self) -> None:
        shelf = shelves.create_shelf("Bye")
        shelves.delete_shelf(shelf["id"])
        self.assertEqual(shelves.list_shelves(), [])