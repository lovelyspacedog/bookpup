import unittest

from lib.client_ip import client_key


class ClientIpTests(unittest.TestCase):
    def test_direct_peer(self) -> None:
        self.assertEqual(client_key("203.0.113.5", {}), "203.0.113.5")

    def test_ignores_forwarded_when_not_loopback(self) -> None:
        hdrs = {"X-Forwarded-For": "1.2.3.4"}
        self.assertEqual(client_key("203.0.113.5", hdrs), "203.0.113.5")

    def test_trusts_xff_from_loopback(self) -> None:
        hdrs = {"X-Forwarded-For": "198.51.100.2, 127.0.0.1"}
        self.assertEqual(client_key("127.0.0.1", hdrs), "198.51.100.2")

    def test_trusts_forwarded_from_loopback(self) -> None:
        hdrs = {"Forwarded": 'for=198.51.100.3;proto=https;by=127.0.0.1'}
        self.assertEqual(client_key("127.0.0.1", hdrs), "198.51.100.3")


if __name__ == "__main__":
    unittest.main()