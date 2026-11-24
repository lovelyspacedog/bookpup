"""Unauthenticated JSON endpoints."""

from __future__ import annotations

import urllib.error
from urllib.parse import parse_qs, urlparse

from .. import cover_search, reader_ai
from ..core import CONFIG_DIR, IRC_MOCK, VERSION, load_config, public_base_url
from ..irc_worker import worker
from .. import slskd_client, xdcc_search
from ..wttr import fetch_wttr_line, normalize_us_zip
from ._types import RequestHandler


def route_public_config(handler: RequestHandler) -> None:
    cfg = load_config()
    handler.send_json(
        200,
        {
            "version": VERSION,
            "irc_mock": IRC_MOCK,
            "koreader_sync_url": public_base_url(cfg),
        },
    )


def route_public_health(handler: RequestHandler) -> None:
    cfg = load_config()
    writable = False
    try:
        probe = CONFIG_DIR / ".health_probe"
        probe.write_text("ok")
        probe.unlink(missing_ok=True)
        writable = True
    except OSError:
        writable = False
    irc = worker.health_snapshot()
    xdcc = xdcc_search.health_probe()
    slskd = slskd_client.health_probe()
    handler.send_json(
        200,
        {
            "ok": writable,
            "version": VERSION,
            "irc_mock": IRC_MOCK,
            "xdcc_mock": xdcc_search.XDCC_MOCK,
            "slskd_mock": slskd_client.SLSKD_MOCK,
            "xdcc_search": xdcc,
            "soulseek": slskd,
            "config_dir_writable": writable,
            "public_url": public_base_url(cfg),
            **irc,
        },
    )


def route_public_weather(handler: RequestHandler) -> None:
    qs = parse_qs(urlparse(handler.path).query)
    zip5 = normalize_us_zip((qs.get("zip") or [""])[0])
    if not zip5:
        handler.send_json(400, {"error": "invalid zip"})
        return
    try:
        line = fetch_wttr_line(zip5)
    except (urllib.error.URLError, OSError, TimeoutError):
        handler.send_json(502, {"error": "weather unavailable"})
        return
    handler.send_json(200, {"zip": zip5, "line": line})


def route_public_capabilities(handler: RequestHandler) -> None:
    cfg = handler.config or load_config()
    handler.send_json(
        200,
        {
            "cover_image_search": cover_search.cover_image_search_enabled(cfg),
            "koreader_sync": True,
            "reader_ai": reader_ai.status().get("ready", False),
        },
    )