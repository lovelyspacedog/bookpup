import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.irc_client import IrcSession, irc_trailing_message, is_search_no_matches_notice


class IrcNoticeParseTest(unittest.TestCase):
    def test_trailing_from_searchbot_notice(self) -> None:
        line = (
            ":SearchBot!services NOTICE BookPup_kprxwd :"
            "<<SearchBot>> Sorry, your search for \"The Skyrim Library\" "
            "returned no matches. Search took 1.16 seconds."
        )
        msg = irc_trailing_message(line)
        self.assertIn("returned no matches", msg)
        self.assertTrue(is_search_no_matches_notice(msg))

    def test_notice_target_is_us(self) -> None:
        sess = IrcSession("x", 6667, nick="BookPup_kprxwd")
        line = ":SearchBot NOTICE BookPup_kprxwd :hello"
        self.assertTrue(sess._notice_to_us(line))
        self.assertFalse(sess._notice_to_us(":SearchBot NOTICE #ebooks :hello"))


if __name__ == "__main__":
    unittest.main()