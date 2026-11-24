"""Sideload tokens and delivery options."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.device_delivery as device_delivery
import lib.library as library
import lib.sideload_tokens as sideload_tokens
import lib.user_paths as user_paths


class SideloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        sideload_tokens._TOKEN_FILE = core.CONFIG_DIR / "sideload_tokens.json"
        core._config = {
            "username": "book",
            "password": "test",
            "port": 18478,
            "library_quota_bytes": 50 * 1024 * 1024,
        }
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"test","port":18478,"library_quota_bytes":52428800}\n'
        )
        accounts.reload_accounts()
        user_paths.set_user("book")
        user_paths.ensure_user_dirs("book")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def _register_epub(self) -> str:
        data = b"PK\x03\x04" + b"x" * 48
        item = library.add_upload(data, "test.epub", title_hint="Test EPUB")
        return library.register_item(item["id"], {"title": "Test EPUB"})["id"]

    def test_token_create_and_consume(self) -> None:
        item_id = self._register_epub()
        owner = user_paths.current_user()
        tok = sideload_tokens.create_token(owner, item_id, "source")
        row = sideload_tokens.consume_token(tok["token"])
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["item_id"], item_id)
        self.assertIsNone(sideload_tokens.peek_token(tok["token"]))

    def test_delivery_options_epub(self) -> None:
        item_id = self._register_epub()
        opts = device_delivery.delivery_options(item_id)
        self.assertTrue(any(o["id"] == "source" for o in opts))

    def test_kindle_email_validation(self) -> None:
        self.assertEqual(accounts.normalize_kindle_email("you@kindle.com"), "you@kindle.com")
        with self.assertRaises(ValueError):
            accounts.normalize_kindle_email("you@gmail.com")


if __name__ == "__main__":
    unittest.main()