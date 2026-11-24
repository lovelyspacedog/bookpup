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
import lib.library_shares as library_shares
import lib.pack_chat as pack_chat
import lib.transfer as transfer
import lib.user_paths as user_paths


class LibrarySharesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        library_shares.SHARES_FILE = core.CONFIG_DIR / "library_shares.json"
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
        library_shares.reload_for_tests()
        user_paths.set_user("alice")
        library.add_bytes("Alice book", b"a" * 400, "epub", source="registered")
        user_paths.set_user("bob")
        library.add_bytes("Bob book", b"b" * 400, "epub", source="registered")
        user_paths.set_user(None)

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        library_shares.reload_for_tests()
        self.tmp.cleanup()
        core._config = None

    def test_request_accept_lend_and_catalog(self) -> None:
        row = library_shares.create_request("alice", "bob")
        self.assertEqual(row["status"], "pending")
        self.assertFalse(library_shares.can_read("alice", "bob"))
        accepted = library_shares.accept_grant(row["id"], "bob", "lend")
        self.assertEqual(accepted["status"], "active")
        self.assertEqual(accepted["mode"], "lend")
        self.assertTrue(library_shares.can_read("alice", "bob"))
        self.assertFalse(library_shares.can_take("alice", "bob"))

    def test_give_take_copy(self) -> None:
        row = library_shares.create_request("alice", "bob")
        library_shares.accept_grant(row["id"], "bob", "give")
        self.assertTrue(library_shares.can_take("alice", "bob"))
        user_paths.set_user("bob")
        bob_item = library.list_items()[0]
        transfer.send_library_item("bob", "alice", bob_item["id"])
        user_paths.set_user("alice")
        self.assertEqual(len(library.list_items()), 2)

    def test_owner_invite_accept(self) -> None:
        row = library_shares.create_owner_invite("alice", "bob", "lend")
        self.assertEqual(row.get("initiated_by"), "owner")
        accepted = library_shares.accept_invite_as_requester(row["id"], "bob", "lend")
        self.assertEqual(accepted["status"], "active")
        self.assertTrue(library_shares.can_read("bob", "alice"))

    def test_revoke_blocks_read(self) -> None:
        row = library_shares.create_request("alice", "bob")
        library_shares.accept_grant(row["id"], "bob", "lend")
        library_shares.revoke_grant(row["id"], "bob", is_admin=False)
        self.assertFalse(library_shares.can_read("alice", "bob"))

    def test_duplicate_pending_rejected(self) -> None:
        library_shares.create_request("alice", "bob")
        with self.assertRaises(ValueError):
            library_shares.create_request("alice", "bob")


if __name__ == "__main__":
    unittest.main()