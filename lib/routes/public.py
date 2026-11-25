"""Unauthenticated JSON endpoints."""

from __future__ import annotations

from .. import cover_search, kindle_smtp, ops_readiness, reader_ai
from ..core import IRC_MOCK, VERSION, load_config, public_base_url, public_url_configured
from ..irc_worker import worker
from .. import slskd_client, xdcc_search
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


def route_public_ready(handler: RequestHandler) -> None:
    handler.send_json(200, ops_readiness.build_ready())


def _health_verbose(qs: dict) -> bool:
    raw = qs.get("verbose")
    if raw is None:
        return False
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return str(raw).strip().lower() in ("1", "true", "yes")


def route_public_health(handler: RequestHandler, qs: dict | None = None) -> None:
    cfg = load_config()
    writable = ops_readiness.config_dir_writable()
    payload: dict = {
        "ok": writable,
        "version": VERSION,
        "config_dir_writable": writable,
        "public_url": public_base_url(cfg),
        "public_url_configured": public_url_configured(cfg),
        "kindle_smtp": kindle_smtp.smtp_configured(cfg),
    }
    if _health_verbose(qs or {}):
        irc = worker.health_snapshot()
        payload.update(
            {
                "irc_mock": IRC_MOCK,
                "xdcc_mock": xdcc_search.XDCC_MOCK,
                "slskd_mock": slskd_client.SLSKD_MOCK,
                "xdcc_search": xdcc_search.health_probe(),
                "soulseek": slskd_client.health_probe(),
                **irc,
            }
        )
    handler.send_json(200, payload)


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