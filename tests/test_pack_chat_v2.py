import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.pack_chat as pack_chat
import lib.user_paths as user_paths


class PackChatV2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        pack_chat.PACK_CHAT_FILE = core.CONFIG_DIR / "pack_chat.json"
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
        accounts.create_user("bob", "pw2", quota_bytes=10_000_000)
        user_paths.set_user("alice")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        pack_chat._loaded = False
        self.tmp.cleanup()
        core._config = None

    def test_reply_and_reaction(self) -> None:
        root = pack_chat.append_message("alice", "Hello pack")
        pack_chat.append_message("bob", "Hi", parent_id=root)
        row = pack_chat.toggle_reaction(root, "alice", "paw")
        self.assertIn("paw", row.get("reactions", {}))
        snap = pack_chat.snapshot(viewer="alice")
        self.assertEqual(len(snap["messages"]), 2)
        self.assertIsNotNone(snap["messages"][1].get("parent"))

    def test_reply_to_reply_rejected(self) -> None:
        root = pack_chat.append_message("alice", "A")
        child = pack_chat.append_message("bob", "B", parent_id=root)
        with self.assertRaises(ValueError):
            pack_chat.append_message("alice", "C", parent_id=child)


if __name__ == "__main__":
    unittest.main()