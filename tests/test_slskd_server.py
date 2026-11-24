import unittest
from unittest import mock

import lib.core as core
import lib.slskd_client as slskd_client


class SlskdServerReadyTest(unittest.TestCase):
    def test_server_is_logged_in_flags(self) -> None:
        self.assertTrue(slskd_client._server_is_logged_in({"isLoggedIn": True}))
        self.assertTrue(slskd_client._server_is_logged_in({"state": "LoggedIn"}))
        self.assertFalse(slskd_client._server_is_logged_in({"state": "Disconnected"}))

    def test_ensure_connects_when_disconnected(self) -> None:
        states = [
            {"state": "Disconnected", "isLoggedIn": False, "isTransitioning": False},
            {"state": "LoggingIn", "isLoggedIn": False, "isTransitioning": True},
            {"state": "LoggedIn", "isLoggedIn": True},
        ]
        with (
            mock.patch.object(slskd_client, "SLSKD_MOCK", False),
            mock.patch.object(slskd_client, "get_server_state", side_effect=states),
            mock.patch.object(slskd_client, "connect_server") as connect,
            mock.patch.object(slskd_client, "time") as tmock,
        ):
            tmock.monotonic.side_effect = [0.0, 0.1, 0.2, 0.3]
            tmock.sleep = mock.Mock()
            slskd_client.ensure_server_ready(timeout=10)
        connect.assert_called_once()

    def test_search_timeout_ms_for_slskd_api(self) -> None:
        with mock.patch.object(core, "load_config", return_value={"soulseek_search_timeout_sec": 20}):
            self.assertEqual(slskd_client.search_timeout_ms(), 20000)

    def test_list_downloads_flattens_directory_files(self) -> None:
        payload = [
            {
                "username": "peer",
                "directories": [
                    {
                        "directory": "Books/Eragon",
                        "files": [
                            {
                                "id": "tid-1",
                                "username": "peer",
                                "filename": "Books\\Eragon\\book.epub",
                                "state": "Queued",
                            }
                        ],
                    }
                ],
            }
        ]
        with (
            mock.patch.object(slskd_client, "SLSKD_MOCK", False),
            mock.patch.object(slskd_client, "_request", return_value=payload),
        ):
            rows = slskd_client.list_downloads()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "tid-1")

    def test_find_download_matches_path_separators(self) -> None:
        row = {
            "id": "tid-2",
            "username": "peer",
            "filename": "Books\\Eragon\\book.epub",
        }
        with mock.patch.object(slskd_client, "list_downloads", return_value=[row]):
            found = slskd_client.find_download_transfer("peer", "Books/Eragon/book.epub")
        self.assertEqual(found["id"], "tid-2")

    def test_state_ok_compound_succeeded(self) -> None:
        self.assertTrue(slskd_client._state_ok("Completed, Succeeded"))

    def test_state_ok_rejected_compound_not_success(self) -> None:
        self.assertFalse(slskd_client._state_ok("Completed, Rejected"))
        self.assertTrue(slskd_client._state_fail("Completed, Rejected"))


if __name__ == "__main__":
    unittest.main()