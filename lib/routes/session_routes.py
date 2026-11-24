"""Authenticated session snapshot."""

from __future__ import annotations

from .. import accounts, irc_targets, quota, soulseek_limits, transfer
from ..core import public_base_url
from ._types import RequestHandler


def handle_get(handler: RequestHandler, path: str, _qs: dict) -> bool:
    owner = handler._current_user
    admin = handler._is_admin
    if path == "/api/users":
        handler.send_json(200, {"users": transfer.household_usernames()})
        return True
    if path == "/api/session":
        usage = quota.library_usage_for(owner)
        base = public_base_url(handler.config)
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
                "kindle_email": accounts.kindle_email_for(owner),
                "soulseek_limits": soulseek_limits.limits_for_user(owner),
            },
        )
        return True
    return False