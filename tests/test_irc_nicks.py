import re
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.irc_nicks import nick_pool, random_nick


class IrcNickTests(unittest.TestCase):
    def test_pool_size(self) -> None:
        pool = nick_pool()
        self.assertGreaterEqual(len(pool), 1000)
        self.assertEqual(len(pool), len(set(pool)))

    def test_random_nick_format(self) -> None:
        pat = re.compile(r"^[A-Z][a-z]+[A-Z][a-z]+$")
        for _ in range(20):
            nick = random_nick()
            self.assertLessEqual(len(nick), 30, nick)
            self.assertRegex(nick, pat, nick)


if __name__ == "__main__":
    unittest.main()