"""xdccsearch.com index client (stdlib HTTP, no extra deps)."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .core import load_config, user_agent

# IRC host per indexer network when bot API is skipped or fails (fetch resolves when needed).
NETWORK_IRC_SERVER: dict[str, str] = {
    "rizon": "irc.rizon.net",
    "abjects": "irc.abjects.net",
    "abandoned-irc": "irc.abandoned-irc.net",
    "undernet": "us.undernet.org",
    "scenep2p": "irc.scenep2p.com",
    "terrachat": "irc.terrachat.net",
}

DEFAULT_BASE_URL = "https://xdccsearch.com"
DEFAULT_TIMEOUT = 30.0
SEARCH_LIMIT = 50

XDCC_MOCK = os.environ.get("BOOKPUP_XDCC_MOCK", "").strip() in ("1", "true", "yes")

_bot_server_cache: dict[str, str] = {}


class XdccSearchError(Exception):
    """HTTP or API failure talking to the index."""


class XdccSearchDisabledError(XdccSearchError):
    """Index disabled in config or env."""


def xdcc_search_enabled() -> bool:
    if XDCC_MOCK:
        return True
    cfg = load_config()
    if cfg.get("xdcc_search_enabled") is False:
        return False
    env = os.environ.get("BOOKPUP_XDCC_SEARCH_ENABLED", "").strip().lower()
    if env in ("0", "false", "no"):
        return False
    return True


def base_url() -> str:
    cfg = load_config()
    raw = str(cfg.get("xdcc_search_url") or os.environ.get("BOOKPUP_XDCC_SEARCH_URL") or "").strip()
    if not raw:
        return DEFAULT_BASE_URL
    url = raw.rstrip("/")
    if "www.xdccsearch" in url.lower():
        url = url.replace("www.xdccsearch", "xdccsearch")
    return url


def _timeout() -> float:
    cfg = load_config()
    try:
        return float(cfg.get("xdcc_search_timeout") or DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT


def _format_size(num_bytes: int | float | None) -> str | None:
    if num_bytes is None:
        return None
    try:
        n = float(num_bytes)
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    units = ("B", "KB", "MB", "GB", "TB")
    u = 0
    while n >= 1024 and u < len(units) - 1:
        n /= 1024
        u += 1
    if u == 0:
        return f"{int(n)} {units[u]}"
    return f"{n:.1f} {units[u]}"


def _xdcc_row_target(network: str) -> str:
    net = (network or "").strip().lower().replace(" ", "-")
    return f"xdcc:{net}" if net else "xdcc:unknown"


def _network_irc_defaults(network: str) -> tuple[int, bool]:
    """Default IRC port/TLS for common XDCC networks."""
    n = (network or "").strip().lower()
    if n in ("rizon",):
        return 6667, False
    if n in ("abjects", "abandoned-irc"):
        return 6667, False
    if n in ("undernet",):
        return 6667, False
    if n in ("irchighway", "irc-highway", "irchighway"):
        return 6667, False
    return 6667, False


def _http_get_json(path: str, *, cache: dict[str, str] | None = None) -> Any:
    if not xdcc_search_enabled():
        raise XdccSearchDisabledError("XDCC index search is disabled")
    url = f"{base_url()}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent(),
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=_timeout(), context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise XdccSearchError(f"Index HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise XdccSearchError(f"Index unreachable: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise XdccSearchError("Index returned invalid JSON") from exc


def log_xdcc_search_begin(query: str, *, owner: str | None = None) -> None:
    from . import irc_feed

    q = (query or "").strip()
    irc_feed.append_out("xdccsearch", f'index search "{q[:200]}"')
    irc_feed.append_session(f'XDCC index: searching for "{q[:120]}"…', owner=owner)


def log_xdcc_search_done(query: str, count: int, *, owner: str | None = None) -> None:
    from . import irc_feed

    q = (query or "").strip()
    irc_feed.append_session(
        f'XDCC index: {count} match(es) for "{q[:80]}"',
        owner=owner,
    )


def log_xdcc_search_failed(query: str, reason: str, *, owner: str | None = None) -> None:
    from . import irc_feed

    irc_feed.append_session(
        f'XDCC index failed ({query[:60]!r}): {reason[:160]}',
        owner=owner,
    )


def network_default_server(network: str) -> str:
    n = (network or "").strip().lower()
    return NETWORK_IRC_SERVER.get(n, "")


def resolve_bot_server(bot_id: str, *, cache: dict[str, str] | None = None) -> str:
    bid = (bot_id or "").strip()
    if not bid:
        raise XdccSearchError("Missing bot_id")
    store = cache if cache is not None else _bot_server_cache
    if bid in store:
        return store[bid]
    if XDCC_MOCK:
        server = "irc.mock.xdcc"
        store[bid] = server
        return server
    payload = _http_get_json(f"/api/bots/{urllib.parse.quote(bid, safe='')}")
    if not isinstance(payload, dict) or not payload.get("success"):
        raise XdccSearchError("Bot lookup failed")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise XdccSearchError("Bot lookup missing data")
    server = str(data.get("server") or "").strip()
    if not server:
        raise XdccSearchError("Bot lookup missing server")
    store[bid] = server
    return server


def _map_item(item: dict[str, Any], *, cache: dict[str, str]) -> dict[str, Any]:
    bot_id = str(item.get("bot_id") or "").strip()
    botname = str(item.get("botname") or "").strip()
    network = str(item.get("network") or "").strip()
    channel = str(item.get("channel") or "").strip()
    filename = str(item.get("filename") or "").strip()
    try:
        slot = int(item.get("slot"))
    except (TypeError, ValueError):
        slot = 0
    port, use_tls = _network_irc_defaults(network)
    # Resolve IRC host at fetch time (not during search — up to 50 bot lookups stalled Sniff).
    server_host = network_default_server(network)
    xdcc_blob = {
        "bot_id": bot_id,
        "botname": botname,
        "slot": slot,
        "channel": channel,
        "network": network,
        "server": server_host,
        "port": port,
        "use_tls": use_tls,
    }
    return {
        "download_kind": "xdcc",
        "title": filename,
        "size_hint": _format_size(item.get("size_bytes")),
        "network": network,
        "server": botname or "—",
        "irc_target": _xdcc_row_target(network),
        "command": f"!xdcc #{slot}",
        "xdcc": xdcc_blob,
    }


def search(
    query: str,
    *,
    page: int = 1,
    limit: int = SEARCH_LIMIT,
    bot_cache: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    if XDCC_MOCK:
        from pathlib import Path

        fixture = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "xdcc_search_sample.json"
        if fixture.is_file():
            payload = json.loads(fixture.read_text())
            data = payload.get("data") if isinstance(payload, dict) else payload
            if not isinstance(data, list):
                return []
            cache = bot_cache if bot_cache is not None else {}
            return [_map_item(x, cache=cache) for x in data if isinstance(x, dict)]
        return []
    if not xdcc_search_enabled():
        raise XdccSearchDisabledError("XDCC index search is disabled")
    qs = urllib.parse.urlencode(
        {"query": q, "page": max(1, page), "limit": max(1, min(limit, SEARCH_LIMIT))}
    )
    payload = _http_get_json(f"/api/search?{qs}")
    if not isinstance(payload, dict) or not payload.get("success"):
        raise XdccSearchError("Search failed")
    data = payload.get("data")
    if not isinstance(data, list):
        raise XdccSearchError("Search missing data")
    cache = bot_cache if bot_cache is not None else {}
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            out.append(_map_item(item, cache=cache))
        except XdccSearchError:
            continue
    return out


def ensure_xdcc_server(xdcc: dict[str, Any], *, cache: dict[str, str] | None = None) -> dict[str, Any]:
    """Fill xdcc['server'] from bot API or network default before IRC connect."""
    out = dict(xdcc)
    if str(out.get("server") or "").strip():
        return out
    bid = str(out.get("bot_id") or "").strip()
    if bid:
        try:
            out["server"] = resolve_bot_server(bid, cache=cache)
            return out
        except XdccSearchError:
            pass
    net = str(out.get("network") or "").strip()
    fallback = network_default_server(net)
    if fallback:
        out["server"] = fallback
    return out


def run_search_job(job: dict[str, Any], *, owner: str | None = None) -> None:
    """Execute an XDCC index search job (HTTP only, no IRC worker queue)."""
    from . import irc_feed, jobs
    from . import user_paths
    from .staging import create_staging

    job_id = str(job["id"])
    query = str(job.get("query") or "").strip()
    if owner:
        user_paths.set_user(owner)
    irc_feed.set_job_owner(owner)
    try:
        log_xdcc_search_begin(query, owner=owner)
        job = jobs.load_job(job_id)
        job["state"] = "running"
        jobs.set_irc_status(job_id, "Querying XDCC index…")
        jobs.save_job(job)
        staging_id = job_id
        create_staging(staging_id)
        try:
            rows = search(query)
        except XdccSearchDisabledError as exc:
            job = jobs.load_job(job_id)
            job["results"] = []
            job["result_count"] = 0
            job["staging_id"] = staging_id
            job["search_notice"] = str(exc)[:240]
            job["state"] = "done"
            job.pop("irc_status", None)
            log_xdcc_search_done(query, 0, owner=owner)
            jobs.save_job(job)
            return
        except XdccSearchError as exc:
            log_xdcc_search_failed(query, str(exc), owner=owner)
            job = jobs.load_job(job_id)
            job["state"] = "error"
            job["error"] = str(exc)[:400]
            job.pop("irc_status", None)
            jobs.save_job(job)
            return
        log_xdcc_search_done(query, len(rows), owner=owner)
        job = jobs.load_job(job_id)
        job["results"] = rows
        job["result_count"] = len(rows)
        job["staging_id"] = staging_id
        if not rows:
            job["search_notice"] = f'No XDCC matches for "{query}"'
        job["state"] = "done"
        job.pop("error", None)
        job.pop("irc_status", None)
        jobs.save_job(job)
    finally:
        irc_feed.set_job_owner(None)
        user_paths.set_user(None)


def clear_bot_cache() -> None:
    _bot_server_cache.clear()


def health_probe() -> dict[str, Any]:
    """Best-effort reachability check for /api/health."""
    out: dict[str, Any] = {"enabled": xdcc_search_enabled(), "base_url": base_url()}
    if not out["enabled"] or XDCC_MOCK:
        out["reachable"] = bool(XDCC_MOCK)
        return out
    try:
        payload = _http_get_json("/api/networks")
        out["reachable"] = bool(isinstance(payload, dict) and payload.get("success"))
    except XdccSearchError as exc:
        out["reachable"] = False
        out["error"] = str(exc)[:120]
    return out