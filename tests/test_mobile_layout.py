"""Structural checks for mobile-friendly layout (smoke matrix #11)."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"
CSS = ROOT / "static" / "bookpup.css"


class MobileLayoutTests(unittest.TestCase):
    def test_viewport_meta(self) -> None:
        html = INDEX.read_text()
        self.assertIn("viewport-fit=cover", html)
        self.assertIn("width=device-width", html)

    def test_mobile_css_breakpoints(self) -> None:
        css = CSS.read_text()
        self.assertGreaterEqual(len(re.findall(r"@media\s*\(\s*max-width:\s*40rem", css)), 1)

    def test_tabs_scrollable_mobile_rules(self) -> None:
        css = CSS.read_text()
        block = css[css.find("@media (max-width: 40rem)") :]
        self.assertIn(".bp-tabs", block)
        self.assertTrue(
            "overflow" in block[:4000],
            "mobile block should allow horizontal tab scroll",
        )

    def test_mobile_tabbar_shell(self) -> None:
        html = INDEX.read_text()
        css = CSS.read_text()
        self.assertIn("bp-tabbar-shell", html)
        self.assertIn("tab-more-logout", html)
        self.assertIn("tab-more", html)
        self.assertIn(".bp-tabbar-shell", css)
        self.assertIn("max-width: 100vw", css)

    def test_more_menu_logout_styles(self) -> None:
        css = CSS.read_text()
        self.assertIn(".bp-tab-more-item--exit", css)

    def test_reader_modal_present(self) -> None:
        html = INDEX.read_text()
        self.assertIn('id="reader-modal"', html)
        self.assertIn("bp-reader", html)

    def test_library_view_toggle(self) -> None:
        html = INDEX.read_text()
        self.assertIn('id="lib-view-grid"', html)
        self.assertIn('id="lib-view-list"', html)

    def test_filter_clear_controls(self) -> None:
        html = INDEX.read_text()
        self.assertIn('id="sniff-results-wipe"', html)
        self.assertIn('id="lib-filter-clear"', html)


if __name__ == "__main__":
    unittest.main()