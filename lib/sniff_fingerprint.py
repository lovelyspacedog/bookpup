"""Stable row keys for sniff result diffing (mirrors static/app-search.js sniffRowKey)."""

from __future__ import annotations

from typing import Any

from .title_match import norm_title


def _is_xdcc_row(row: dict[str, Any]) -> bool:
    return row.get("download_kind") == "xdcc" or isinstance(row.get("xdcc"), dict)


def fingerprint_row(row: dict[str, Any]) -> str:
    kind = str(row.get("download_kind") or "")
    network = str(row.get("network") or "")
    command = str(row.get("command") or "")
    title = norm_title(str(row.get("title") or ""))
    bot_slot = ""
    if _is_xdcc_row(row):
        xdcc = row.get("xdcc")
        if isinstance(xdcc, dict) and xdcc.get("botname") is not None:
            bot_slot = f"{xdcc.get('botname')}|{xdcc.get('slot')}"
    return f"{kind}|{network}|{bot_slot}|{command}|{title}"


def fingerprints_for_rows(rows: list[dict[str, Any]]) -> list[str]:
    return [fingerprint_row(r) for r in rows if isinstance(r, dict)]