"""IRC network + channel targets for search, download, and chat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import DEFAULT_IRC_PORT, DEFAULT_IRC_SERVER, load_config

SEARCH_ALL_ID = "all"
XDCC_INDEX_ID = "xdcc:index"
SOULSEEK_INDEX_ID = "soulseek:slskd"
DEFAULT_SEARCH_TARGET = "irchighway:ebooks"

LEGACY_ALIASES: dict[str, str] = {
    "ebooks": "irchighway:ebooks",
    "bookz": "undernet:bookz",
}

# SearchBot no longer answers @search on IRCHighway #bookz; keep old ids for saved jobs.
RETIRED_SEARCH_TARGETS: dict[str, str] = {
    "irchighway:bookz": DEFAULT_SEARCH_TARGET,
}

# Sniff source picker: full label, hint (under control), compact label (narrow viewports).
SNIFF_SOURCE_COPY: dict[str, tuple[str, str, str]] = {
    DEFAULT_SEARCH_TARGET: (
        "Main trail · IRCHighway #ebooks (recommended)",
        "Sends @search on IRCHighway #ebooks for novels and mainstream EPUB/MOBI. "
        "Bots reply with a DCC zip of !commands. Best first pick for most book sniffing.",
        "Main trail · IRCHighway #ebooks",
    ),
    SEARCH_ALL_ID: (
        "Every ebook net · all IRC @search channels",
        "Runs your query on IRCHighway #ebooks, Undernet #bookz, and Rizon #ebookz, "
        "then merges hits (Network column). Slower; no XDCC. Chat/bark disabled while this is selected.",
        "Every ebook net · IRC @search (all)",
    ),
    XDCC_INDEX_ID: (
        "Warez yard · XDCC index (xdccsearch)",
        "HTTP metasearch across warez IRC—not @search. Video, comics, archives, packs, and more "
        "(not limited to ebooks). Fetch uses XDCC send to each row's bot.",
        "Warez yard · XDCC index",
    ),
    SOULSEEK_INDEX_ID: (
        "Peer trail · Soulseek (slskd)",
        "Live search on the Soulseek network via household slskd. Results share one Soulseek login; "
        "per-user sniff and fetch caps apply (admins exempt from personal caps).",
        "Peer trail · Soulseek",
    ),
    "undernet:bookz": (
        "Backup trail · Undernet #bookz",
        "Undernet ebook bots via @search. Good when IRCHighway is empty; Undernet may be pickier "
        "from a VPS—prefer !get rows when offered.",
        "Backup trail · Undernet #bookz",
    ),
    "rizon:ebookz": (
        "Side trail · Rizon #ebookz",
        "Rizon #ebookz @search for an extra ebook catalog. Useful for duplicates, gaps, or "
        "titles missing on IRCHighway.",
        "Side trail · Rizon #ebookz",
    ),
}


@dataclass(frozen=True)
class IrcTarget:
    id: str
    network: str
    channel: str
    server: str
    port: int
    use_tls: bool

    @property
    def display(self) -> str:
        return f"{self.network} · {self.channel}"

    def session_key(self) -> tuple[str, int, bool]:
        return (self.server, self.port, self.use_tls)


def _highway_server_port_tls() -> tuple[str, int, bool]:
    cfg = load_config()
    return (
        str(cfg.get("irc_server", DEFAULT_IRC_SERVER)),
        int(cfg.get("irc_port", DEFAULT_IRC_PORT)),
        bool(cfg.get("irc_tls")),
    )


def _registry() -> dict[str, dict[str, Any]]:
    hw_server, hw_port, hw_tls = _highway_server_port_tls()
    return {
        "irchighway:ebooks": {
            "network": "IRCHighway",
            "channel": "#ebooks",
            "server": hw_server,
            "port": hw_port,
            "use_tls": hw_tls,
        },
        "undernet:bookz": {
            "network": "Undernet",
            "channel": "#bookz",
            # Round-robin irc.undernet.org often lands on hosts blocked from shared VPS egress.
            "server": "us.undernet.org",
            "port": 6667,
            "use_tls": False,
        },
        "rizon:ebookz": {
            "network": "Rizon",
            "channel": "#ebookz",
            "server": "irc.rizon.net",
            "port": 6667,
            "use_tls": False,
        },
    }


def normalize_channel_id(raw: str | None) -> str:
    key = (raw or DEFAULT_SEARCH_TARGET).strip().lower()
    key = LEGACY_ALIASES.get(key, key)
    return RETIRED_SEARCH_TARGETS.get(key, key)


def is_search_all(raw: str | None) -> bool:
    return normalize_channel_id(raw) == SEARCH_ALL_ID


def is_xdcc_search(raw: str | None) -> bool:
    return normalize_channel_id(raw) == XDCC_INDEX_ID


def is_soulseek_search(raw: str | None) -> bool:
    return normalize_channel_id(raw) == SOULSEEK_INDEX_ID


def is_xdcc_row_target(raw: str | None) -> bool:
    cid = normalize_channel_id(raw)
    return cid.startswith("xdcc:") and cid != XDCC_INDEX_ID


def known_ids() -> frozenset[str]:
    return frozenset(_registry().keys()) | frozenset({XDCC_INDEX_ID})


def known_search_channel_ids() -> frozenset[str]:
    return known_ids() | frozenset({SEARCH_ALL_ID, XDCC_INDEX_ID, SOULSEEK_INDEX_ID})


def search_target_ids() -> tuple[str, ...]:
    """Order used for Sniff all networks."""
    return tuple(_registry().keys())


def resolve_target(raw: str | None) -> IrcTarget:
    cid = normalize_channel_id(raw)
    if cid == SEARCH_ALL_ID:
        raise ValueError("Cannot open IRC session for search-all pseudo target")
    if cid == XDCC_INDEX_ID:
        return IrcTarget(
            id=XDCC_INDEX_ID,
            network="XDCC",
            channel="",
            server="",
            port=0,
            use_tls=False,
        )
    if cid == SOULSEEK_INDEX_ID:
        return IrcTarget(
            id=SOULSEEK_INDEX_ID,
            network="Soulseek",
            channel="",
            server="",
            port=0,
            use_tls=False,
        )
    if is_xdcc_row_target(cid):
        raise ValueError(f"XDCC fetch requires connection metadata on the job (target {raw!r})")
    reg = _registry()
    if cid not in reg:
        raise ValueError(f"Unknown IRC channel target: {raw!r}")
    meta = reg[cid]
    return IrcTarget(
        id=cid,
        network=str(meta["network"]),
        channel=str(meta["channel"]),
        server=str(meta["server"]),
        port=int(meta["port"]),
        use_tls=bool(meta["use_tls"]),
    )


def list_targets() -> list[dict[str, str | int | bool]]:
    reg = _registry()
    order = (
        DEFAULT_SEARCH_TARGET,
        "undernet:bookz",
        "rizon:ebookz",
    )

    def row(tid: str, *, pseudo: bool = False) -> dict[str, str | int | bool]:
        copy = SNIFF_SOURCE_COPY.get(tid)
        label = copy[0] if copy else tid
        hint = copy[1] if copy else ""
        short_label = copy[2] if copy else label
        if pseudo:
            network = "All" if tid == SEARCH_ALL_ID else "XDCC"
            return {
                "id": tid,
                "label": label,
                "short_label": short_label,
                "hint": hint,
                "network": network,
                "channel": "",
                "server": "",
                "port": 0,
                "use_tls": False,
                "recommended": False,
                "default": False,
            }
        meta = reg[tid]
        if not copy:
            label = f'{meta["network"]} · {meta["channel"]}'
        return {
            "id": tid,
            "label": label,
            "short_label": short_label,
            "hint": hint,
            "network": str(meta["network"]),
            "channel": str(meta["channel"]),
            "server": str(meta["server"]),
            "port": int(meta["port"]),
            "use_tls": bool(meta["use_tls"]),
            "recommended": tid == DEFAULT_SEARCH_TARGET,
            "default": tid == DEFAULT_SEARCH_TARGET,
        }

    out: list[dict[str, str | int | bool]] = [row(DEFAULT_SEARCH_TARGET)]
    out.append(row(SEARCH_ALL_ID, pseudo=True))
    out.append(row(XDCC_INDEX_ID, pseudo=True))
    out.append(row(SOULSEEK_INDEX_ID, pseudo=True))
    for tid in order:
        if tid == DEFAULT_SEARCH_TARGET:
            continue
        out.append(row(tid))
    return out