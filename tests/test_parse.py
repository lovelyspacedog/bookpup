import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.search_results import parse_result_line, parse_results_text


class ParseResultsTest(unittest.TestCase):
    def test_dash_size(self) -> None:
        row = parse_result_line(
            "!bald Author - Title.epub - 142.1 KB"
        )
        assert row is not None
        self.assertEqual(row.server, "bald")
        self.assertEqual(row.command, "!bald Author - Title.epub")
        self.assertIn("142.1", row.size_hint or "")

    def test_fused_size(self) -> None:
        row = parse_result_line("!AlternaServ Testimony by Noreen Gosch.pdf3.6MB")
        assert row is not None
        self.assertEqual(row.command, "!AlternaServ Testimony by Noreen Gosch.pdf")
        self.assertEqual(row.size_hint, "3.6MB")

    def test_fused_epub_digit_suffix(self) -> None:
        row = parse_result_line(
            "!Bsk Title With Purpose,.epub170.52KB"
        )
        assert row is not None
        self.assertEqual(row.command, "!Bsk Title With Purpose,.epub")
        self.assertNotIn(".epub1", row.command)

    def test_no_bare_digit_fused(self) -> None:
        row = parse_result_line("!Bsk Something.epub224.81KB")
        assert row is not None
        self.assertTrue(row.command.endswith(".epub"))
        self.assertEqual(row.size_hint, "224.81KB")

    def test_fixture_file(self) -> None:
        text = (ROOT / "tests/fixtures/sample_results.txt").read_text()
        rows = parse_results_text(text)
        self.assertEqual(len(rows), 3)

    def test_undernet_catalog_enriches_get_rows(self) -> None:
        text = """\
1059831 | Arthur S. Way - The Lay of the Nibelung Men | Project Gutenberg
!get 1059831
!Oatmeal Arthur S. Way - The Lay of the Nibelung Men [PG-59831].epub  ::INFO:: ON-DEMAND
"""
        rows = parse_results_text(text)
        self.assertEqual(len(rows), 2)
        get_row = next(r for r in rows if r.server == "get")
        self.assertEqual(get_row.title, "Arthur S. Way - The Lay of the Nibelung Men")
        self.assertEqual(get_row.command, "!get 1059831")
        oat = next(r for r in rows if r.server == "Oatmeal")
        self.assertNotIn("ON-DEMAND", oat.title)


if __name__ == "__main__":
    unittest.main()