import time
import unittest

from lib.irc_bot_health import BotHealthTracker


class IrcBotHealthTest(unittest.TestCase):
    def test_banner_updates_slots(self) -> None:
        h = BotHealthTracker(stale_seconds=60)
        h.ingest_channel_message(
            "Type: @adiroman For My List Of: 2,981 Files | Slots: 0/4 | Queued: 2"
        )
        self.assertFalse(h.is_stale("adiroman"))
        warn = h.warn_full_slots("adiroman")
        self.assertIsNotNone(warn)
        self.assertIn("0/4", warn or "")

    def test_stale_after_threshold(self) -> None:
        h = BotHealthTracker(stale_seconds=1)
        h.ingest_channel_message("Type: @Oatmeal For My List | Slots: 1/2 | Queued: 0")
        time.sleep(1.2)
        self.assertTrue(h.is_stale("oatmeal"))

    def test_unknown_not_stale(self) -> None:
        h = BotHealthTracker(stale_seconds=60)
        self.assertFalse(h.is_stale("missing-bot"))


if __name__ == "__main__":
    unittest.main()