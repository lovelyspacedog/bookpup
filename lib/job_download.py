"""Validate search result rows before queuing a fetch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FetchValidation:
    command: str | None
    xdcc: dict[str, Any] | None = None
    soulseek: dict[str, Any] | None = None


def row_is_xdcc(row: dict[str, Any]) -> bool:
    if str(row.get("download_kind") or "").lower() == "xdcc":
        return True
    cmd = str(row.get("command") or "").strip().lower()
    return cmd.startswith("!xdcc")


def row_is_soulseek(row: dict[str, Any]) -> bool:
    if str(row.get("download_kind") or "").lower() == "soulseek":
        return True
    return isinstance(row.get("soulseek"), dict)


def validate_xdcc_row(row: dict[str, Any]) -> dict[str, Any]:
    blob = row.get("xdcc")
    if not isinstance(blob, dict):
        raise ValueError("XDCC row missing xdcc metadata")
    botname = str(blob.get("botname") or "").strip()
    server = str(blob.get("server") or "").strip()
    channel = str(blob.get("channel") or "").strip()
    try:
        slot = int(blob.get("slot"))
    except (TypeError, ValueError):
        slot = 0
    bot_id = str(blob.get("bot_id") or "").strip()
    if not botname or not channel or slot < 1:
        raise ValueError("Incomplete XDCC metadata on row")
    if not server and not bot_id:
        raise ValueError("XDCC row missing bot_id or server")
    network = str(blob.get("network") or "").strip()
    try:
        port = int(blob.get("port") or 6667)
    except (TypeError, ValueError):
        port = 6667
    use_tls = bool(blob.get("use_tls"))
    return {
        "bot_id": bot_id,
        "botname": botname,
        "slot": slot,
        "channel": channel,
        "network": network,
        "server": server,
        "port": port,
        "use_tls": use_tls,
    }


def validate_soulseek_row(row: dict[str, Any]) -> dict[str, Any]:
    blob = row.get("soulseek")
    if not isinstance(blob, dict):
        raise ValueError("Soulseek row missing soulseek metadata")
    username = str(blob.get("username") or "").strip()
    filename = str(blob.get("filename") or "").strip()
    try:
        size = int(blob.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if not username or not filename:
        raise ValueError("Incomplete Soulseek metadata on row")
    return {
        "username": username,
        "filename": filename,
        "size": size,
        "search_id": str(blob.get("search_id") or "").strip(),
    }


def validate_fetch_row(row: dict[str, Any]) -> FetchValidation:
    if row_is_soulseek(row):
        blob = validate_soulseek_row(row)
        cmd = str(row.get("command") or "soulseek").strip() or "soulseek"
        return FetchValidation(command=cmd, soulseek=blob)
    if row_is_xdcc(row):
        blob = validate_xdcc_row(row)
        cmd = str(row.get("command") or f"!xdcc #{blob['slot']}")
        return FetchValidation(command=cmd, xdcc=blob)
    command = str(row.get("command") or "").strip()
    if not command.startswith("!"):
        raise ValueError("Invalid IRC command")
    return FetchValidation(command=command)