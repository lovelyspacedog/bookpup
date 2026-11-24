import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from lib import core
from lib import pack_chat


class PackChatStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.ensure_dirs()
        pack_chat.PACK_CHAT_FILE = core.CONFIG_DIR / "pack_chat.json"
        with pack_chat._lock:
            pack_chat._loaded = False
            pack_chat._messages.clear()
            pack_chat._deletions.clear()
            pack_chat._presence.clear()
            pack_chat._next_id = 1
            pack_chat._del_seq = 0

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_append_and_snapshot(self) -> None:
        mid = pack_chat.append_message("alice", "hello pack")
        self.assertEqual(mid, 1)
        snap = pack_chat.snapshot(after=0, del_after=0, touch_user="alice")
        self.assertEqual(len(snap["messages"]), 1)
        self.assertEqual(snap["messages"][0]["text"], "hello pack")
        self.assertEqual(snap["latest_id"], 1)

    def test_owner_can_delete(self) -> None:
        mid = pack_chat.append_message("alice", "remove me")
        pack_chat.delete_message(mid, "alice", is_admin=False)
        snap = pack_chat.snapshot(after=0, del_after=0)
        self.assertEqual(snap["messages"], [])
        self.assertIn(mid, snap["removed"])

    def test_non_owner_forbidden(self) -> None:
        mid = pack_chat.append_message("alice", "mine")
        with self.assertRaises(PermissionError):
            pack_chat.delete_message(mid, "bob", is_admin=False)

    def test_admin_can_delete_any(self) -> None:
        mid = pack_chat.append_message("alice", "mine")
        pack_chat.delete_message(mid, "admin", is_admin=True)
        snap = pack_chat.snapshot(del_after=0)
        self.assertIn(mid, snap["removed"])

    @mock.patch("lib.pack_chat.transfer.household_usernames", return_value=["alice", "bob"])
    def test_presence_online(self, _mock_users: mock.MagicMock) -> None:
        pack_chat.touch_presence("alice")
        snap = pack_chat.snapshot(touch_user="alice")
        row = next(p for p in snap["presence"] if p["username"] == "alice")
        self.assertTrue(row["online"])

    @mock.patch("lib.pack_chat.transfer.household_usernames", return_value=["alice"])
    def test_presence_offline_after_ttl(self, _mock_users: mock.MagicMock) -> None:
        pack_chat.touch_presence("alice")
        with pack_chat._lock:
            pack_chat._presence["alice"] = time.time() - pack_chat.PRESENCE_TTL_SECONDS - 5
        snap = pack_chat.snapshot()
        row = next(p for p in snap["presence"] if p["username"] == "alice")
        self.assertFalse(row["online"])

    def test_persist_round_trip(self) -> None:
        pack_chat.append_message("alice", "persisted")
        with pack_chat._lock:
            pack_chat._loaded = False
        snap = pack_chat.snapshot(after=0)
        self.assertEqual(len(snap["messages"]), 1)


if __name__ == "__main__":
    unittest.main()