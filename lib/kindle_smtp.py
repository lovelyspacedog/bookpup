"""Household SMTP send-to-Kindle (one shared relay, e.g. Gmail)."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from . import accounts
from .core import load_config

# Gmail attachment cap; Kindle email allows larger but relay is usually Gmail.
ATTACHMENT_MAX_BYTES = 24 * 1024 * 1024
DEFAULT_HOST = "smtp.gmail.com"
DEFAULT_PORT = 587


def smtp_configured(cfg: dict | None = None) -> bool:
    c = cfg if cfg is not None else load_config()
    if not c.get("smtp_enabled"):
        return False
    user = str(c.get("smtp_user") or "").strip()
    password = str(c.get("smtp_password") or "").strip()
    return bool(user and password)


def _smtp_settings(cfg: dict) -> tuple[str, int, str, str, str]:
    host = str(cfg.get("smtp_host") or DEFAULT_HOST).strip() or DEFAULT_HOST
    port = int(cfg.get("smtp_port") or DEFAULT_PORT)
    user = str(cfg.get("smtp_user") or "").strip()
    password = str(cfg.get("smtp_password") or "").strip()
    from_addr = str(cfg.get("smtp_from") or "").strip() or user
    if not user or not password:
        raise ValueError("SMTP is not configured on this server")
    return host, port, user, password, from_addr


def send_kindle_attachment(
    *,
    to_address: str,
    subject: str,
    body_text: str,
    file_path: Path,
    attachment_name: str,
    content_type: str | None = None,
) -> None:
    to_address = accounts.normalize_kindle_email(to_address) or ""
    if not to_address:
        raise ValueError("Save your Send-to-Kindle address under Your tag")
    if not file_path.is_file():
        raise FileNotFoundError("Book file missing")
    size = file_path.stat().st_size
    if size > ATTACHMENT_MAX_BYTES:
        raise ValueError(
            f"File is too large for email ({size // (1024 * 1024)} MB; "
            f"max {ATTACHMENT_MAX_BYTES // (1024 * 1024)} MB). Use the download link instead."
        )
    cfg = load_config()
    host, port, user, password, from_addr = _smtp_settings(cfg)
    data = file_path.read_bytes()
    ctype = (content_type or "application/octet-stream").split(";", 1)[0].strip()
    if "/" in ctype:
        maintype, subtype = ctype.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_address
    msg["Subject"] = subject[:200]
    msg.set_content(body_text[:4000])
    msg.add_attachment(
        data,
        maintype=maintype,
        subtype=subtype,
        filename=attachment_name[:180],
    )
    context = ssl.create_default_context()
    use_tls = cfg.get("smtp_starttls", True)
    with smtplib.SMTP(host, port, timeout=120) as smtp:
        smtp.ehlo()
        if use_tls:
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(user, password)
        smtp.send_message(msg)