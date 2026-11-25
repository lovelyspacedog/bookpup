import unittest

from lib.irc_client import (
    DccOffer,
    _search_dcc_pick_index,
    is_oatmeal_interim_search_dcc_filename,
    is_search_results_dcc_filename,
)


class IrcDccFilterTest(unittest.TestCase):
    def test_search_result_names(self) -> None:
        self.assertTrue(
            is_search_results_dcc_filename("SearchBot_results_for__glen_duncan.txt.zip")
        )
        self.assertTrue(is_search_results_dcc_filename("foo.txt.zip"))
        self.assertFalse(is_search_results_dcc_filename("Wolf.epub"))
        self.assertFalse(is_search_results_dcc_filename("raw.epub"))

    def test_oatmeal_interim_name(self) -> None:
        self.assertTrue(
            is_oatmeal_interim_search_dcc_filename(
                "Oatmeal_Search_Rowling_Philosopher_s_Stone_fj91gw7p.txt.zip"
            )
        )
        self.assertFalse(is_oatmeal_interim_search_dcc_filename("SearchBot_results.txt.zip"))

    def test_search_dcc_prefers_searchbot_over_oatmeal(self) -> None:
        offers = [
            DccOffer("Oatmeal_Search_foo.txt.zip", "1.2.3.4", 1, 900),
            DccOffer("SearchBot_results_for__foo.txt.zip", "5.6.7.8", 2, 800),
        ]
        idx = _search_dcc_pick_index(offers, allow_oatmeal=False)
        self.assertEqual(idx, 1)

    def test_search_dcc_waits_when_only_oatmeal(self) -> None:
        offers = [DccOffer("Oatmeal_Search_foo.txt.zip", "1.2.3.4", 1, 900)]
        self.assertIsNone(_search_dcc_pick_index(offers, allow_oatmeal=False))
        self.assertEqual(_search_dcc_pick_index(offers, allow_oatmeal=True), 0)


if __name__ == "__main__":
    unittest.main()