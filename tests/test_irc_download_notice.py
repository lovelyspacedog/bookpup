import unittest

from lib.irc_client import (
    IrcSession,
    is_catalog_zero_matches_notice,
    is_download_failure_notice,
    is_fetch_abort_notice,
)


class IrcDownloadNoticeTest(unittest.TestCase):
    def test_oatmeal_not_found(self) -> None:
        msg = "File not found in the licensed catalogue. Use !search <title>."
        self.assertTrue(is_download_failure_notice(msg))

    def test_pg_no_epub(self) -> None:
        msg = (
            "This work has no EPUB available.\n"
            "Source: https://www.gutenberg.org/ebooks/10991"
        )
        self.assertTrue(is_download_failure_notice(msg))

    def test_other_notice(self) -> None:
        self.assertFalse(is_download_failure_notice("Searching for foo"))

    def test_catalogue_zero_is_fetch_abort_not_licensed_fail(self) -> None:
        msg = (
            'Your search for "foo.epub" returned 0 matches in the Oatmeal catalogue. '
            "Search took 1.0 seconds."
        )
        self.assertTrue(is_catalog_zero_matches_notice(msg))
        self.assertTrue(is_fetch_abort_notice(msg))
        self.assertFalse(is_download_failure_notice(msg))

    def test_abort_download_on_oatmeal_catalogue_zero(self) -> None:
        sess = IrcSession("x", 6667, nick="BookPup_test")
        msg = (
            'Your search for "foo.mobi" returned 0 matches in the Oatmeal catalogue. '
            "Search took 1.69 seconds."
        )
        sess._arm_book_dcc_wait()
        try:
            sess._maybe_abort_download(msg)
            self.assertTrue(sess._book_aborted.is_set())
        finally:
            sess._disarm_book_dcc_wait()

    def test_abort_download_when_armed_before_dcc_wait(self) -> None:
        sess = IrcSession("x", 6667, nick="BookPup_test")
        msg = "File not found in the licensed catalogue. Use !search <title>."
        sess._arm_book_dcc_wait()
        try:
            sess._maybe_abort_download(msg)
            self.assertTrue(sess._book_aborted.is_set())
        finally:
            sess._disarm_book_dcc_wait()


if __name__ == "__main__":
    unittest.main()