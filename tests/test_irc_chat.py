import os
import unittest

os.environ["BOOKPUP_IRC_MOCK"] = "1"

import lib.core as core
from lib.irc_worker import IrcWorker


class IrcChatSanitizeTest(unittest.TestCase):
    def setUp(self) -> None:
        core.IRC_MOCK = True
        import lib.irc_worker as iw

        iw.core.IRC_MOCK = True
        self.w = IrcWorker()

    def test_rejects_bang(self) -> None:
        with self.assertRaises(ValueError):
            self.w.send_chat("alice", "ebooks", "!get something")

    def test_mock_posts_to_feed(self) -> None:
        from lib import irc_feed

        irc_feed.append(direction="sys", kind="session", text="reset")
        before = irc_feed.snapshot(after=0)["latest_id"]
        self.w.send_chat("bob", "bookz", "hello everyone")
        ev = [e for e in irc_feed.snapshot(after=before)["events"] if e.get("dir") == "out"]
        self.assertTrue(any(e.get("text") == "hello everyone" for e in ev))

    def test_disconnect_when_idle(self) -> None:
        self.assertFalse(self.w.disconnect_now(owner="bob"))


class IrcChatLivePathTest(unittest.TestCase):
    """Live send_chat path (non-mock): must not re-acquire worker lock and hang."""

    def setUp(self) -> None:
        core.IRC_MOCK = False
        import lib.irc_worker as iw

        iw.core.IRC_MOCK = False
        self.w = IrcWorker()

    def test_send_chat_returns_without_worker_lock_deadlock(self) -> None:
        class StubSession:
            def __init__(self) -> None:
                self.last: tuple[str, str] | None = None

            def privmsg(self, target: str, text: str) -> None:
                self.last = (target, text)

        stub = StubSession()

        def fake_ensure(*_args, **_kwargs):
            return stub

        self.w._ensure_session = fake_ensure  # type: ignore[method-assign]
        self.w.send_chat("frungi", "rizon:ebookz", "Meow")
        self.assertEqual(stub.last, ("#ebookz", "Meow"))


if __name__ == "__main__":
    unittest.main()