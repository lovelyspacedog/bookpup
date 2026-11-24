import socket
import unittest
from unittest.mock import patch

from lib.irc_client import IrcSession


class IrcConnectTimeoutTest(unittest.TestCase):
    def test_connect_clears_socket_read_timeout(self) -> None:
        session = IrcSession("irc.example", 6667, channels=("#bookz",))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(12.0)
        try:

            def wake_connected() -> None:
                session._connected.set()

            class FakeThread:
                def __init__(self, *args, **kwargs) -> None:
                    pass

                def start(self) -> None:
                    wake_connected()

            with patch.object(session, "_open_tcp", return_value=sock):
                with patch.object(session, "_send"):
                    with patch("lib.irc_client.threading.Thread", FakeThread):
                        with patch("lib.irc_client.time.sleep"):
                            session.connect()
            self.assertIsNone(sock.gettimeout())
        finally:
            session.close()
            sock.close()


if __name__ == "__main__":
    unittest.main()