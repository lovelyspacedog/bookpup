import unittest

from lib.irc_commands import adapt_download_command, resolve_download_command, serving_bot_nick


class IrcCommandsTest(unittest.TestCase):
    def test_serving_bot_nick_xdcc_tag(self) -> None:
        self.assertEqual(
            serving_bot_nick("!Pondering-Ebooks2 Anonymous - Naughty Puppies.rar"),
            "pondering-ebooks2",
        )

    def test_serving_bot_nick_local_skipped(self) -> None:
        self.assertIsNone(serving_bot_nick("!get 4242"))
        self.assertIsNone(serving_bot_nick("@search foo"))

    def test_serving_bot_oatmeal_after_adapt(self) -> None:
        cmd = adapt_download_command(
            "undernet:bookz",
            "!Horla Glen Duncan - Title.epub",
        )
        self.assertEqual(serving_bot_nick(cmd), "oatmeal")

    def test_irchighway_unchanged(self) -> None:
        cmd = "!Bsk Author - Title.epub"
        self.assertEqual(adapt_download_command("irchighway:bookz", cmd), cmd)

    def test_undernet_bsk_to_oatmeal(self) -> None:
        cmd = "!Bsk El ultimo hombre lobo - Glen Duncan.epub"
        self.assertEqual(
            adapt_download_command("undernet:bookz", cmd),
            "!Oatmeal El ultimo hombre lobo - Glen Duncan.epub",
        )

    def test_undernet_get_unchanged(self) -> None:
        self.assertEqual(adapt_download_command("undernet:bookz", "!get 1068077"), "!get 1068077")

    def test_undernet_resolves_get_from_results(self) -> None:
        results = [
            {
                "title": "El ultimo hombre lobo - Glen Duncan.epub",
                "command": "!get 4242",
            },
            {
                "title": "Other book",
                "command": "!Bsk El ultimo hombre lobo - Glen Duncan.epub",
            },
        ]
        cmd, hint, redirect = resolve_download_command(
            "undernet:bookz",
            "!Bsk El ultimo hombre lobo - Glen Duncan.epub",
            title="El ultimo hombre lobo - Glen Duncan.epub",
            search_results=results,
        )
        self.assertEqual(cmd, "!get 4242")
        self.assertIsNotNone(hint)
        self.assertIsNone(redirect)

    def test_undernet_horla_redirects_to_highway(self) -> None:
        all_rows = [
            {
                "irc_target": "undernet:bookz",
                "title": "Glen Duncan - Talulla Rising (US) (epub).epub",
                "command": "!Horla Glen Duncan - [Last Werewolf 02] - Talulla Rising (US) (epub).epub",
            },
            {
                "irc_target": "irchighway:ebooks",
                "title": "Glen Duncan - [Last Werewolf 02] - Talulla Rising (US) (epub).epub",
                "command": "!Horla Glen Duncan - [Last Werewolf 02] - Talulla Rising (US) (epub).epub",
            },
        ]
        undernet_only = [all_rows[0]]
        cmd, hint, redirect = resolve_download_command(
            "undernet:bookz",
            all_rows[0]["command"],
            title=all_rows[0]["title"],
            search_results=undernet_only,
            all_search_results=all_rows,
        )
        self.assertEqual(cmd, all_rows[1]["command"])
        self.assertEqual(redirect, "irchighway:ebooks")
        self.assertIn("fetch on", hint or "")


if __name__ == "__main__":
    unittest.main()