import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.library as library
import lib.library_shares as library_shares
import lib.pack_chat as pack_chat
import lib.user_paths as user_paths


class PackChatAttachmentsTest(unittest.TestCase):
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
        library.add_bytes("Book", b"x" * 200, "epub", source="calibre_import")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        library_shares.reload_for_tests()
        pack_chat._loaded = False
        self.tmp.cleanup()
        core._config = None

    def test_book_attachment_dm(self) -> None:
        item = library.list_items()[0]
        mid = pack_chat.append_message(
            "alice",
            "Check this",
            to="bob",
            attachments=[{"type": "library_book", "item_id": item["id"], "intent": "recommend"}],
        )
        self.assertGreater(mid, 0)
        snap = pack_chat.snapshot(viewer="bob")
        msg = snap["messages"][-1]
        self.assertEqual(msg["attachments"][0]["type"], "library_book")

    def test_no_attach_to_bugbot(self) -> None:
        with self.assertRaises(ValueError):
            pack_chat.append_message(
                "alice",
                "x",
                to="bugbot",
                attachments=[{"type": "kennel_invite", "requester": "bob"}],
            )

    @mock.patch("lib.transfer.send_library_item")
    def test_pack_chat_attachments_claim_copy_race(self, mock_send: mock.MagicMock) -> None:
        item = library.list_items()[0]
        mid = pack_chat.append_message(
            "alice",
            "take it",
            to="bob",
            attachments=[
                {
                    "type": "library_book",
                    "item_id": item["id"],
                    "owner": "alice",
                    "intent": "offer_copy",
                }
            ],
        )
        gate = threading.Event()
        release = threading.Event()

        def slow_copy(*_a, **_k):
            gate.set()
            release.wait(timeout=2)
            return {"id": "copy-1", "title": "Book"}

        mock_send.side_effect = slow_copy
        results: list[str] = []

        def claim() -> None:
            try:
                pack_chat.claim_attachment_copy(mid, 0, "bob")
                results.append("ok")
            except ValueError as exc:
                results.append(str(exc))

        first = threading.Thread(target=claim)
        second = threading.Thread(target=claim)
        first.start()
        self.assertTrue(gate.wait(timeout=2))
        second.start()
        release.set()
        first.join(timeout=5)
        second.join(timeout=5)
        self.assertEqual(len([r for r in results if r == "ok"]), 1)
        self.assertEqual(len([r for r in results if "already claimed" in r]), 1)

    def test_kennel_invite_attachment(self) -> None:
        mid = pack_chat.append_message(
            "alice",
            "",
            to="bob",
            attachments=[{"type": "kennel_invite", "requester": "bob", "mode_suggested": "lend"}],
        )
        self.assertGreater(mid, 0)
        snap = pack_chat.snapshot(viewer="bob")
        att = snap["messages"][-1]["attachments"][0]
        self.assertEqual(att["type"], "kennel_invite")
        self.assertTrue(att.get("actions", {}).get("can_accept_invite"))


if __name__ == "__main__":
    unittest.main()