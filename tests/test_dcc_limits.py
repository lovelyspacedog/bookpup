import tempfile
import unittest
from pathlib import Path

from lib.irc_client import DccOffer, DownloadRequestError, assert_dcc_offer_size


class DccLimitTest(unittest.TestCase):
    def test_rejects_oversized_offer(self) -> None:
        offer = DccOffer("big.epub", "127.0.0.1", 1234, 50_000_000)
        with self.assertRaises(DownloadRequestError):
            assert_dcc_offer_size(offer, 1_000_000)

    def test_accepts_within_cap(self) -> None:
        offer = DccOffer("ok.epub", "127.0.0.1", 1234, 500_000)
        assert_dcc_offer_size(offer, 1_000_000)


if __name__ == "__main__":
    unittest.main()