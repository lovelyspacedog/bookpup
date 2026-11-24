import os
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core


class PublicUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.ensure_dirs()
        self._env_public = os.environ.pop("BOOKPUP_PUBLIC_URL", None)
        core._config = None

    def tearDown(self) -> None:
        if self._env_public is not None:
            os.environ["BOOKPUP_PUBLIC_URL"] = self._env_public
        else:
            os.environ.pop("BOOKPUP_PUBLIC_URL", None)
        self.tmp.cleanup()
        core._config = None

    def test_default_from_config(self) -> None:
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"x","irc_server":"h","irc_port":6667,'
            '"public_url":"https://books.example.com"}'
        )
        core._config = None
        self.assertEqual(core.public_base_url(), "https://books.example.com")

    def test_env_overrides_config(self) -> None:
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"x","irc_server":"h","irc_port":6667,'
            '"public_url":"https://books.example.com"}'
        )
        core._config = None
        os.environ["BOOKPUP_PUBLIC_URL"] = "https://env.example.org/"
        self.assertEqual(core.public_base_url(), "https://env.example.org")

    def test_adds_https_scheme(self) -> None:
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"x","irc_server":"h","irc_port":6667,'
            '"public_url":"bookpup.example.com"}'
        )
        core._config = None
        self.assertEqual(core.public_base_url(), "https://bookpup.example.com")

    def test_empty_when_unset(self) -> None:
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"x","irc_server":"h","irc_port":6667}'
        )
        core._config = None
        self.assertEqual(core.public_base_url(), "")
        self.assertFalse(core.public_url_configured())

    def test_user_agent_without_public_url(self) -> None:
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"x","irc_server":"h","irc_port":6667}'
        )
        core._config = None
        ua = core.user_agent()
        self.assertIn(f"BookPup/{core.VERSION}", ua)
        self.assertNotIn("+https://", ua)


if __name__ == "__main__":
    unittest.main()