import unittest

from lib.login_limit import MAX_FAILURES, check_allowed, record_failure, record_success


class LoginLimitTests(unittest.TestCase):
    def tearDown(self) -> None:
        record_success("127.0.0.1")
        record_success("test-client")

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


if __name__ == "__main__":
    unittest.main()