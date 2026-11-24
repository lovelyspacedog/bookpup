import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.auth as auth
import lib.core as core


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.ensure_dirs()
        core.SESSIONS_FILE = core.CONFIG_DIR / "sessions.json"
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"secret123","irc_server":"x","irc_port":6667}'
        )
        core._config = None
        auth._sessions.clear()
        if core.SESSIONS_FILE.is_file():
            core.SESSIONS_FILE.unlink()

    def tearDown(self) -> None:
        self.tmp.cleanup()
        auth._sessions.clear()

    def test_sessions_persist_on_disk(self) -> None:
        token = auth.create_token("book")
        self.assertTrue(core.SESSIONS_FILE.is_file())
        auth._sessions.clear()
        self.assertIsNone(auth.session_user(f"Bearer {token}"))
        self.assertEqual(auth.bootstrap_sessions(), 1)
        self.assertEqual(auth.session_user(f"Bearer {token}"), "book")

    def test_login_token(self) -> None:
        self.assertTrue(auth.verify_credentials("book", "secret123"))
        self.assertFalse(auth.verify_credentials("book", "wrong"))
        token = auth.create_token("book")
        self.assertEqual(auth.session_user(f"Bearer {token}"), "book")
        self.assertTrue(auth.check_bearer(f"Bearer {token}"))
        auth.revoke_token(token)
        self.assertFalse(auth.check_bearer(f"Bearer {token}"))


if __name__ == "__main__":
    unittest.main()