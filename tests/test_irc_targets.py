import os
import tempfile
import unittest
from pathlib import Path

import lib.core as core
from lib import irc_targets


class IrcTargetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_config = core.CONFIG_FILE
        core.CONFIG_DIR = Path(self._tmpdir.name)
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core._config = None
        core._config_mtime = None
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"x","irc_server":"irc.example.net","irc_port":6697,"irc_tls":true}\n'
        )
        os.chmod(core.CONFIG_FILE, 0o600)

    def tearDown(self) -> None:
        core.CONFIG_FILE = self._orig_config
        core._config = None
        core._config_mtime = None
        self._tmpdir.cleanup()

    def test_legacy_normalize(self) -> None:
        self.assertEqual(irc_targets.normalize_channel_id("ebooks"), "irchighway:ebooks")
        self.assertEqual(irc_targets.normalize_channel_id("bookz"), "undernet:bookz")
        self.assertEqual(
            irc_targets.normalize_channel_id("irchighway:bookz"),
            irc_targets.DEFAULT_SEARCH_TARGET,
        )
        self.assertEqual(irc_targets.normalize_channel_id("undernet:bookz"), "undernet:bookz")

    def test_irchighway_uses_config(self) -> None:
        t = irc_targets.resolve_target("irchighway:ebooks")
        self.assertEqual(t.server, "irc.example.net")
        self.assertEqual(t.port, 6697)
        self.assertTrue(t.use_tls)
        self.assertEqual(t.channel, "#ebooks")
        self.assertEqual(t.display, "IRCHighway · #ebooks")

    def test_undernet_and_rizon(self) -> None:
        u = irc_targets.resolve_target("undernet:bookz")
        self.assertEqual(u.server, "us.undernet.org")
        self.assertEqual(u.channel, "#bookz")
        r = irc_targets.resolve_target("rizon:ebookz")
        self.assertEqual(r.server, "irc.rizon.net")
        self.assertEqual(r.channel, "#ebookz")

    def test_list_has_all_and_three_search_networks(self) -> None:
        rows = irc_targets.list_targets()
        ids = [t["id"] for t in rows]
        self.assertEqual(len(ids), 6)
        self.assertNotIn("irchighway:bookz", ids)
        self.assertEqual(ids[0], irc_targets.DEFAULT_SEARCH_TARGET)
        self.assertEqual(ids[1], irc_targets.SEARCH_ALL_ID)
        self.assertIn(irc_targets.XDCC_INDEX_ID, ids)
        self.assertIn(irc_targets.SOULSEEK_INDEX_ID, ids)
        self.assertTrue(rows[0].get("recommended"))
        self.assertIn("recommended", str(rows[0].get("label")))
        self.assertIn("rizon:ebookz", ids)

    def test_search_all_normalize(self) -> None:
        self.assertTrue(irc_targets.is_search_all("all"))

    def test_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            irc_targets.resolve_target("nope:channel")


if __name__ == "__main__":
    unittest.main()