"""Dig tab API."""

from __future__ import annotations

from .. import dig_picks
from ._types import RequestHandler


def handle_get(handler: RequestHandler, path: str, _qs: dict) -> bool:
    if path != "/api/dig-picks":
        return False
    payload = dig_picks.build_dig_picks(handler._current_user)
    handler.send_json(200, payload)
    return True