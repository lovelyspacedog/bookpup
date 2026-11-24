import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lib import bugbot
from lib import core
from lib import pack_chat


class BugBotTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["BOOKPUP_BOT_REPLY_DELAY"] = "0"
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.ensure_dirs()
        pack_chat.PACK_CHAT_FILE = core.CONFIG_DIR / "pack_chat.json"
        bugbot.STATE_FILE = core.CONFIG_DIR / "bugbot_state.json"
        bugbot.INBOX_FILE = core.CONFIG_DIR / "bug_inbox.json"
        with pack_chat._lock:
            pack_chat._loaded = False
            pack_chat._messages.clear()
            pack_chat._deletions.clear()
            pack_chat._next_id = 1
        with bugbot._lock:
            bugbot._state_loaded = False
            bugbot._intro_seen.clear()
            bugbot._inbox_loaded = False
            bugbot._inbox_reports.clear()
            bugbot._inbox_next_id = 1

    def tearDown(self) -> None:
        os.environ.pop("BOOKPUP_BOT_REPLY_DELAY", None)
        self.tmp.cleanup()

    @mock.patch("lib.bugbot.accounts.get_user", return_value={"username": "alice", "enabled": True})
    def test_intro_once(self, _mock: mock.MagicMock) -> None:
        self.assertTrue(bugbot.ensure_intro("alice"))
        self.assertFalse(bugbot.ensure_intro("alice"))
        snap = pack_chat.snapshot(after=0, viewer="alice")
        intros = [m for m in snap["messages"] if m.get("kind") == "bugbot_intro"]
        self.assertEqual(len(intros), 1)

    @mock.patch("lib.bugbot.accounts.get_user", return_value={"username": "alice", "enabled": True})
    def test_report_inbox_and_ack(self, _mock: mock.MagicMock) -> None:
        with mock.patch("lib.pack_chat.transfer._validate_recipient"):
            mid = pack_chat.append_message("alice", "buttons overlap", to=pack_chat.BUGBOT_SENDER)
        rid = bugbot.on_user_report("alice", "buttons overlap", pack_message_id=mid)
        self.assertEqual(rid, 1)
        inbox = bugbot.list_inbox()
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["text"], "buttons overlap")
        snap = pack_chat.snapshot(after=0, viewer="alice")
        acks = [m for m in snap["messages"] if m.get("kind") == "bugbot_ack"]
        self.assertEqual(len(acks), 1)

    @mock.patch("lib.bugbot.accounts.get_user", return_value={"username": "alice", "enabled": True})
    def test_dismiss_report(self, _mock: mock.MagicMock) -> None:
        bugbot.on_user_report("alice", "broken")
        bugbot.dismiss_report(1)
        self.assertEqual(bugbot.list_inbox(), [])

    @mock.patch(
        "lib.pack_chat.accounts.get_user",
        return_value={"username": "alice", "enabled": True},
    )
    @mock.patch("lib.bugbot.accounts.get_user", return_value={"username": "alice", "enabled": True})
    def test_clear_reposts_intro(self, _mock_bug: mock.MagicMock, _mock_pc: mock.MagicMock) -> None:
        bugbot.ensure_intro("alice")
        with mock.patch("lib.pack_chat.transfer._validate_recipient"):
            pack_chat.append_message("alice", "oops", to=pack_chat.BUGBOT_SENDER)
        bugbot.on_clear_thread("alice")
        snap = pack_chat.snapshot(after=0, viewer="alice")
        texts = [m["text"] for m in snap["messages"]]
        self.assertEqual(texts, [bugbot.INTRO_TEXT])
        self.assertNotIn("oops", texts)

    @mock.patch(
        "lib.pack_chat.accounts.get_user",
        return_value={"username": "alice", "enabled": True},
    )
    @mock.patch("lib.pack_chat.transfer._validate_recipient")
    def test_dm_thread_visible(self, _mock_val: mock.MagicMock, _mock_user: mock.MagicMock) -> None:
        pack_chat.append_virtual_dm(pack_chat.BUGBOT_SENDER, "alice", "intro", kind="bugbot_intro")
        pack_chat.append_message("alice", "help", to=pack_chat.BUGBOT_SENDER)
        snap = pack_chat.snapshot(after=0, viewer="alice")
        self.assertEqual(len(snap["messages"]), 2)
        peers = pack_chat.list_dm_peers("alice")
        self.assertTrue(any(p["username"] == pack_chat.BUGBOT_SENDER for p in peers))


if __name__ == "__main__":
    unittest.main()