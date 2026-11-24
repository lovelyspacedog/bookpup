import unittest

from lib import irc_feed


class IrcFeedTest(unittest.TestCase):
    def test_strip_and_snapshot(self) -> None:
        seq = irc_feed.append(direction="out", kind="privmsg", text="hello", target="#ebooks")
        self.assertGreater(seq, 0)
        snap = irc_feed.snapshot(after=0)
        self.assertTrue(snap["events"])

    def test_owner_tag(self) -> None:
        irc_feed.set_job_owner("alice")
        try:
            irc_feed.append_in_line(":x PRIVMSG #ebooks :hi")
        finally:
            irc_feed.set_job_owner(None)
        ev = irc_feed.snapshot(after=0)["events"][-1]
        self.assertEqual(ev.get("owner"), "alice")

    def test_snapshot_viewer_filter(self) -> None:
        start = irc_feed.snapshot(after=0)["latest_id"]
        irc_feed.append(
            direction="out",
            kind="privmsg",
            text="for alice",
            target="#ebooks",
            owner="alice",
        )
        irc_feed.append(
            direction="out",
            kind="privmsg",
            text="for bob",
            target="#ebooks",
            owner="bob",
        )
        irc_feed.append(
            direction="in",
            kind="privmsg",
            text="no owner tag",
            target="#ebooks",
        )
        alice = irc_feed.snapshot(after=start, viewer="alice")["events"]
        self.assertEqual(len(alice), 2)
        self.assertTrue(any(e.get("owner") == "alice" for e in alice))
        self.assertTrue(any(not e.get("owner") for e in alice))
        self.assertFalse(any(e.get("owner") == "bob" for e in alice))


if __name__ == "__main__":
    unittest.main()