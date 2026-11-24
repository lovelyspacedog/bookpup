import unittest

from lib.title_match import match_library_title, titles_likely_same


class TitleMatchTests(unittest.TestCase):
    def test_same_norm(self) -> None:
        self.assertTrue(titles_likely_same("The Hobbit", "the hobbit"))

    def test_substring(self) -> None:
        self.assertTrue(
            titles_likely_same(
                "Duncan Glen - Pagan Theology",
                "Pagan Theology - Duncan Glen.epub",
            )
        )

    def test_match_library(self) -> None:
        items = [{"id": "a", "title": "Neuromancer", "authors": "Gibson"}]
        hit = match_library_title("Neuromancer (William Gibson).epub", items)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["id"], "a")

    def test_no_match_shared_the_only(self) -> None:
        self.assertFalse(
            titles_likely_same(
                "The Name of the Wind",
                "The Wise Man's Fear",
            )
        )

    def test_no_match_series_neighbor(self) -> None:
        self.assertFalse(
            titles_likely_same(
                "Mistborn The Final Empire",
                "Mistborn The Well of Ascension",
            )
        )

    def test_dune_not_children(self) -> None:
        self.assertFalse(titles_likely_same("Children of Dune", "Dune"))

    def test_picks_best_among_many(self) -> None:
        items = [
            {"id": "a", "title": "Elantris", "authors": "Brandon Sanderson"},
            {"id": "b", "title": "Warbreaker", "authors": "Brandon Sanderson"},
        ]
        hit = match_library_title("Elantris - Brandon Sanderson.epub", items)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["id"], "a")


if __name__ == "__main__":
    unittest.main()