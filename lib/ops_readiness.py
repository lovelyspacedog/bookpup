"""Operator readiness vs liveness (optional dependency checks)."""

from __future__ import annotations

import shutil
from typing import Any

from . import convert
from . import slskd_client
from .core import CONFIG_DIR, IRC_MOCK
from .irc_worker import worker


def config_dir_writable() -> bool:
    try:
        probe = CONFIG_DIR / ".health_probe"
        probe.write_text("ok")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def tool_probes() -> dict[str, dict[str, Any]]:
    calibre = convert._find_ebook_convert()
    return {
        "calibre": {
            "available": calibre is not None,
            "optional": True,
        },
        "7z": {"available": bool(shutil.which("7z")), "optional": True},
        "unrar": {"available": bool(shutil.which("unrar")), "optional": True},
    }


def build_ready() -> dict[str, Any]:
    """Readiness: can this instance serve traffic (IRC worker, configured sidecars)?"""
    worker.start()
    reasons: list[str] = []
    irc = worker.health_snapshot()
    if not irc.get("irc_worker_alive"):
        reasons.append("irc_worker_down")

    slskd = slskd_client.health_probe()
    slskd_required = bool(slskd.get("enabled")) and not slskd_client.SLSKD_MOCK
    if slskd_required:
        if not slskd.get("reachable"):
            reasons.append("slskd_unreachable")
        elif slskd.get("server_logged_in") is False:
            reasons.append("slskd_not_logged_in")

    tools = tool_probes()
    return {
        "ready": len(reasons) == 0,
        "reasons": reasons,
        "config_dir_writable": config_dir_writable(),
        "tools": tools,
        "irc": {
            "irc_worker_alive": bool(irc.get("irc_worker_alive")),
            "irc_connected": bool(irc.get("irc_connected")),
            "irc_mock": IRC_MOCK,
        },
        "soulseek": {
            "enabled": bool(slskd.get("enabled")),
            "reachable": bool(slskd.get("reachable")),
            "server_logged_in": slskd.get("server_logged_in"),
        },
    }