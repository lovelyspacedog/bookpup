"""Kindle SMTP helper."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
import lib.kindle_smtp as kindle_smtp


class KindleSmtpTests(unittest.TestCase):
    def test_smtp_configured(self) -> None:
        self.assertFalse(kindle_smtp.smtp_configured({"smtp_enabled": False}))
        self.assertFalse(
            kindle_smtp.smtp_configured({"smtp_enabled": True, "smtp_user": "a@gmail.com"})
        )
        self.assertTrue(
            kindle_smtp.smtp_configured(
                {
                    "smtp_enabled": True,
                    "smtp_user": "a@gmail.com",
                    "smtp_password": "secret",
                }
            )
        )

    def test_send_calls_smtp(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            f.write(b"PK\x03\x04test")
            path = Path(f.name)
        try:
            with mock.patch.object(kindle_smtp, "load_config") as lc:
                lc.return_value = {
                    "smtp_enabled": True,
                    "smtp_user": "house@gmail.com",
                    "smtp_password": "app-pass",
                    "smtp_host": "smtp.gmail.com",
                    "smtp_port": 587,
                    "smtp_starttls": True,
                }
                with mock.patch("lib.kindle_smtp.smtplib.SMTP") as smtp_cls:
                    smtp = smtp_cls.return_value.__enter__.return_value
                    kindle_smtp.send_kindle_attachment(
                        to_address="you@kindle.com",
                        subject="Test",
                        body_text="hi",
                        file_path=path,
                        attachment_name="t.epub",
                        content_type="application/epub+zip",
                    )
                    smtp.login.assert_called_once()
                    smtp.send_message.assert_called_once()
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()