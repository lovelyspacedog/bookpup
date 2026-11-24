import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from lib import bot_reply
from lib import core
from lib import pack_chat


class BotReplyDelayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.ensure_dirs()
        pack_chat.PACK_CHAT_FILE = core.CONFIG_DIR / "pack_chat.json"
        with pack_chat._lock:
            pack_chat._loaded = False
            pack_chat._messages.clear()
            pack_chat._next_id = 1

    def tearDown(self) -> None:
        os.environ.pop("BOOKPUP_BOT_REPLY_DELAY", None)
        self.tmp.cleanup()

    @mock.patch("lib.bot_reply.random.uniform", return_value=2.5)
    @mock.patch(
        "lib.pack_chat.accounts.get_user",
        return_value={"username": "alice", "enabled": True},
    )
    def test_delayed_reply_thread(self, _user: mock.MagicMock, _uniform: mock.MagicMock) -> None:
        with mock.patch("lib.bot_reply.time.sleep") as sleep:
            bot_reply.schedule_delayed_virtual_dm(
                pack_chat.BUGBOT_SENDER, "alice", "purr", kind="bugbot_ack"
            )
            deadline = time.time() + 1.0
            while time.time() < deadline and not sleep.call_args_list:
                time.sleep(0.02)
        sleep.assert_called_once_with(2.5)
        snap = pack_chat.snapshot(after=0, viewer="alice")
        self.assertEqual(snap["messages"][0]["text"], "purr")


if __name__ == "__main__":
    unittest.main()