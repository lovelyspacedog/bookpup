"""Shared login throttle for API and OPDS/KOReader auth."""

from __future__ import annotations

from ..client_ip import client_key
from ..login_limit import check_allowed, record_failure, record_success
from ._types import RequestHandler


def peer_key(handler: RequestHandler) -> str:
    peer = handler.client_address[0] if handler.client_address else None
    return client_key(peer, handler._header_map())


def block_json(handler: RequestHandler) -> bool:
    allowed, retry = check_allowed(peer_key(handler))
    if allowed:
        return False
    handler.send_json(
        429,
        {
            "error": "Too many auth attempts. Try again later.",
            "retry_after_seconds": retry,
        },
    )
    return True


def block_ko_json(handler: RequestHandler) -> bool:
    allowed, retry = check_allowed(peer_key(handler))
    if allowed:
        return False
    handler.send_ko_json(
        429,
        {
            "code": 2001,
            "message": "Too many auth attempts",
            "retry_after_seconds": retry,
        },
    )
    return True


def note_auth_result(handler: RequestHandler, user: str | None) -> None:
    if user:
        record_success(peer_key(handler))
    else:
        record_failure(peer_key(handler))