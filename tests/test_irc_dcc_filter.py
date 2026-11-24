import unittest

from lib.irc_client import DccOffer, is_search_results_dcc_filename


class IrcDccFilterTest(unittest.TestCase):
    def test_search_result_names(self) -> None:
        self.assertTrue(
            is_search_results_dcc_filename("SearchBot_results_for__glen_duncan.txt.zip")
        )
        self.assertTrue(is_search_results_dcc_filename("foo.txt.zip"))
        self.assertFalse(is_search_results_dcc_filename("Wolf.epub"))
        self.assertFalse(is_search_results_dcc_filename("raw.epub"))


if __name__ == "__main__":
    unittest.main()