import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lib import core
from lib import featurecat
from lib import pack_chat


class FeatureCatTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["BOOKPUP_BOT_REPLY_DELAY"] = "0"
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.ensure_dirs()
        pack_chat.PACK_CHAT_FILE = core.CONFIG_DIR / "pack_chat.json"
        featurecat.STATE_FILE = core.CONFIG_DIR / "featurecat_state.json"
        featurecat.INBOX_FILE = core.CONFIG_DIR / "feature_inbox.json"
        with pack_chat._lock:
            pack_chat._loaded = False
            pack_chat._messages.clear()
            pack_chat._deletions.clear()
            pack_chat._next_id = 1
        with featurecat._lock:
            featurecat._state_loaded = False
            featurecat._intro_seen.clear()
            featurecat._inbox_loaded = False
            featurecat._inbox_reports.clear()
            featurecat._inbox_next_id = 1

    def tearDown(self) -> None:
        os.environ.pop("BOOKPUP_BOT_REPLY_DELAY", None)
        self.tmp.cleanup()

    @mock.patch(
        "lib.featurecat.accounts.get_user",
        return_value={"username": "alice", "enabled": True},
    )
    def test_intro_once(self, _mock: mock.MagicMock) -> None:
        self.assertTrue(featurecat.ensure_intro("alice"))
        self.assertFalse(featurecat.ensure_intro("alice"))
        snap = pack_chat.snapshot(after=0, viewer="alice")
        intros = [m for m in snap["messages"] if m.get("kind") == "featurecat_intro"]
        self.assertEqual(len(intros), 1)

    @mock.patch(
        "lib.featurecat.accounts.get_user",
        return_value={"username": "alice", "enabled": True},
    )
    def test_submission_inbox_and_ack(self, _mock: mock.MagicMock) -> None:
        with mock.patch("lib.pack_chat.transfer._validate_recipient"):
            mid = pack_chat.append_message(
                "alice", "dark mode please", to=pack_chat.FEATURECAT_SENDER
            )
        rid = featurecat.on_user_submission(
            "alice", "dark mode please", pack_message_id=mid
        )
        self.assertEqual(rid, 1)
        inbox = featurecat.list_inbox()
        self.assertEqual(inbox[0]["text"], "dark mode please")
        snap = pack_chat.snapshot(after=0, viewer="alice")
        acks = [m for m in snap["messages"] if m.get("kind") == "featurecat_ack"]
        self.assertEqual(len(acks), 1)


if __name__ == "__main__":
    unittest.main()