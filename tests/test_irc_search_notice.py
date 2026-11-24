import unittest

from lib.irc_client import (
    extract_search_query_from_notice,
    is_search_no_matches_notice,
)


class SearchNoticeTests(unittest.TestCase):
    def test_no_matches_notice(self) -> None:
        msg = (
            '<<SearchBot>> Sorry, your search for "The Skyrim Library" '
            "returned no matches. Search took 1.17 seconds."
        )
        self.assertTrue(is_search_no_matches_notice(msg))
        self.assertEqual(extract_search_query_from_notice(msg), "The Skyrim Library")

    def test_has_matches_not_triggered(self) -> None:
        self.assertFalse(is_search_no_matches_notice("Found 3 matches for foo"))

    def test_undernet_oatmeal_catalogue_zero_is_interim(self) -> None:
        msg = (
            'Your search for "glen duncan" returned 0 matches in the Oatmeal catalogue. '
            "Search took 1.17 seconds."
        )
        self.assertFalse(is_search_no_matches_notice(msg))


if __name__ == "__main__":
    unittest.main()