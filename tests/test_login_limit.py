import json
import tempfile
import unittest
from pathlib import Path

import lib.core as core
from lib.login_limit import MAX_FAILURES, bootstrap_failures, check_allowed, record_failure, record_success


class LoginLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.ensure_dirs()
        import lib.login_limit as login_limit

        login_limit._FAILURES_FILE = core.CONFIG_DIR / "login_throttle.json"
        login_limit._loaded = False
        login_limit._failures.clear()
        bootstrap_failures()

    def tearDown(self) -> None:
        record_success("127.0.0.1")
        record_success("test-client")
        self.tmp.cleanup()

    def test_allows_under_cap(self) -> None:
        for _ in range(MAX_FAILURES - 1):
            record_failure("test-client")
        ok, retry = check_allowed("test-client")
        self.assertTrue(ok)
        self.assertEqual(retry, 0)

    def test_blocks_after_cap(self) -> None:
        for _ in range(MAX_FAILURES):
            record_failure("test-client")
        ok, retry = check_allowed("test-client")
        self.assertFalse(ok)
        self.assertGreater(retry, 0)

    def test_success_clears_failures(self) -> None:
        for _ in range(MAX_FAILURES):
            record_failure("test-client")
        record_success("test-client")
        ok, _ = check_allowed("test-client")
        self.assertTrue(ok)

    def test_proxy_clients_get_separate_buckets(self) -> None:
        from lib.client_ip import client_key
        from lib.login_limit import check_allowed, record_failure

        a = client_key("127.0.0.1", {"X-Forwarded-For": "198.51.100.10"})
        b = client_key("127.0.0.1", {"X-Forwarded-For": "198.51.100.11"})
        self.assertNotEqual(a, b)
        for _ in range(MAX_FAILURES):
            record_failure(a)
        self.assertFalse(check_allowed(a)[0])
        self.assertTrue(check_allowed(b)[0])

    def test_persists_across_restart(self) -> None:
        import lib.login_limit as login_limit

        for _ in range(MAX_FAILURES):
            record_failure("9.9.9.9")
        login_limit._loaded = False
        login_limit._failures.clear()
        bootstrap_failures()
        ok, retry = check_allowed("9.9.9.9")
        self.assertFalse(ok)
        self.assertGreater(retry, 0)
        data = json.loads(login_limit._FAILURES_FILE.read_text())
        self.assertIn("9.9.9.9", data.get("failures", {}))


if __name__ == "__main__":
    unittest.main()