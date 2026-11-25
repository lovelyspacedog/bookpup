import unittest

from lib.irc_fetch_fallback import (
    alternate_irc_targets,
    fallback_search_query,
    pick_best_row,
)


class IrcFetchFallbackTest(unittest.TestCase):
    def test_alternate_targets_excludes_failed(self) -> None:
        alts = alternate_irc_targets("undernet:bookz")
        self.assertNotIn("undernet:bookz", alts)
        self.assertEqual(len(alts), 2)

    def test_fallback_query_from_parent(self) -> None:
        q = fallback_search_query(
            {"title": "Some Book.epub"},
            {"query": "douglas adams"},
        )
        self.assertEqual(q, "douglas adams")

    def test_pick_best_prefers_get(self) -> None:
        rows = [
            {"title": "Other", "command": "!Bsk Other.epub"},
            {
                "title": "Hitchhiker Guide",
                "command": "!get 424242",
            },
        ]
        pick = pick_best_row(
            rows,
            title="Douglas Adams - Hitchhiker Guide.epub",
            command="!Horla Douglas Adams - Hitchhiker Guide.epub",
        )
        self.assertIsNotNone(pick)
        assert pick is not None
        self.assertTrue(pick["command"].startswith("!get"))


if __name__ == "__main__":
    unittest.main()