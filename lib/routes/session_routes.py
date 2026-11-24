"""Authenticated session snapshot."""

from __future__ import annotations

from .. import accounts, irc_targets, kindle_smtp, quota, soulseek_limits, transfer
from ..core import load_config, public_base_url
from ._types import RequestHandler


def handle_get(handler: RequestHandler, path: str, _qs: dict) -> bool:
    owner = handler._current_user
    admin = handler._is_admin
    if path == "/api/users":
        handler.send_json(200, {"users": transfer.household_usernames()})
        return True
    if path == "/api/session":
        usage = quota.library_usage_for(owner)
        cfg = handler.config or load_config()
        base = public_base_url(cfg)
        smtp_on = kindle_smtp.smtp_configured(cfg)
        kindle_to = accounts.kindle_email_for(owner)
        handler.send_json(
            200,
            {
                "username": owner,
                "admin": admin,
                "usage": usage,
                "irc_targets": irc_targets.list_targets(),
                "opds_url": f"{base}/opds",
                "opds_catalog_url": f"{base}/opds/catalog",
                "koreader_sync_url": base,
                "kindle_email": kindle_to,
                "kindle_smtp": smtp_on,
                "kindle_send_ready": bool(smtp_on and kindle_to),
                "soulseek_limits": soulseek_limits.limits_for_user(owner),
            },
        )
        return True
    return False