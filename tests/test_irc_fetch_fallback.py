import unittest

from lib.irc_fetch_fallback import (
    alternate_irc_targets,
    fallback_search_query,
    pick_best_row,
    pick_ranked_rows,
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

    def test_pick_prefers_same_bot_tag(self) -> None:
        original = (
            "!Pondering-Ebooks2 J K Rowling - [Harry Potter 01] - "
            "Harry Potter and the Philosopher's Stone (retail) (epub).rar"
        )
        rows = [
            {
                "title": "HP1 v4.9",
                "command": "!Horla J K Rowling - HP1 (v4.9) (epub).epub",
            },
            {
                "title": "HP1 retail rar",
                "command": (
                    "!Pondering-Ebooks2 J K Rowling - [Harry Potter 01] - "
                    "Harry Potter and the Philosopher's Stone (retail) (epub).rar"
                ),
            },
        ]
        ranked = pick_ranked_rows(
            rows,
            title="Harry Potter and the Philosopher's Stone (retail) (epub).rar",
            command=original,
        )
        self.assertTrue(ranked[0]["command"].startswith("!Pondering-Ebooks2"))


if __name__ == "__main__":
    unittest.main()