import unittest

from lib.sideload_limit import MAX_CONCURRENT_PER_IP, public_download_slot


class SideloadLimitTests(unittest.TestCase):
    def test_caps_concurrent_per_ip(self) -> None:
        ip = "203.0.113.50"
        held = []
        for _ in range(MAX_CONCURRENT_PER_IP):
            ctx = public_download_slot(ip, {})
            ok = ctx.__enter__()
            self.assertTrue(ok)
            held.append(ctx)
        with public_download_slot(ip, {}) as ok:
            self.assertFalse(ok)
        for ctx in held:
            ctx.__exit__(None, None, None)
        with public_download_slot(ip, {}) as ok:
            self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()