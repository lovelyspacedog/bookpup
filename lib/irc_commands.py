"""Per-network IRC download command normalization."""

from __future__ import annotations

import re

from .irc_targets import normalize_channel_id
from .search_results import normalize_download_body

_COMMAND_RE = re.compile(r"^!([A-Za-z0-9_-]+)\s+(.+)$")

# #bookz on Undernet: DCC via !get ID or file via !Oatmeal (not highway !Bsk etc.)
UNDERNET_LOCAL_TAGS = frozenset({"get", "oatmeal", "search", "find"})
# Bots that accept their own !Tag file line on Undernet #bookz (not !Oatmeal rewrite).
UNDERNET_ON_CHANNEL_BOTS = frozenset({"pondering-ebooks2", "peppylion"})
# Channel-local commands with no single xdcc nick to preflight.
_PREFLIGHT_SKIP_TAGS = frozenset({"get", "search", "find"})


def _title_key(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"\[[^\]]+\]", " ", s)
    s = re.sub(r"\.[a-z0-9]{2,5}$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\(us\)|\(retail\)", " ", s, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _title_match_score(key: str, candidate: str) -> int:
    if not key or not candidate:
        return 0
    if key == candidate:
        return 1000
    if key in candidate or candidate in key:
        return min(len(key), len(candidate)) + 200
    key_tokens = set(key.split())
    tok = set(candidate.split())
    if not key_tokens:
        return 0
    overlap = len(key_tokens & tok)
    if overlap >= 3:
        return overlap * 50 + 60
    return overlap * 40


def _match_undernet_get(
    results: list[dict],
    command: str,
    title: str | None,
) -> str | None:
    m = _COMMAND_RE.match((command or "").strip())
    body = m.group(2).strip() if m else ""
    keys = {_title_key(body), _title_key(title or "")}
    keys.discard("")
    if not keys:
        return None
    best_cmd: str | None = None
    best_score = 0
    for row in results:
        cmd = str(row.get("command") or "").strip()
        if not cmd.lower().startswith("!get "):
            continue
        tkey = _title_key(str(row.get("title") or cmd))
        if not tkey:
            continue
        for key in keys:
            score = _title_match_score(key, tkey)
            if score > best_score:
                best_score = score
                best_cmd = cmd
    return best_cmd if best_score >= 60 else None


def _find_native_network_row(
    results: list[dict],
    command: str,
    title: str | None,
) -> tuple[str, str] | None:
    """Undernet often lists foreign !Horla/!Bsk lines; fetch on the row's home network."""
    m = _COMMAND_RE.match((command or "").strip())
    if not m:
        return None
    tag = m.group(1).lower()
    if tag in UNDERNET_LOCAL_TAGS:
        return None
    body = m.group(2).strip()
    keys = {_title_key(body), _title_key(title or "")}
    keys.discard("")
    if not keys:
        return None
    best: tuple[str, str] | None = None
    best_score = 0
    for row in results:
        tid = str(row.get("irc_target") or "")
        if not tid or tid.startswith("undernet:"):
            continue
        cmd = str(row.get("command") or "").strip()
        if not cmd.startswith("!"):
            continue
        rm = _COMMAND_RE.match(cmd)
        if not rm:
            continue
        same_bot = rm.group(1).lower() == tag
        tkey = _title_key(str(row.get("title") or rm.group(2)))
        if not tkey:
            continue
        for key in keys:
            score = _title_match_score(key, tkey)
            if same_bot:
                score += 120
            if score > best_score:
                best_score = score
                best = (cmd, tid)
    if best and best_score >= 60:
        return best
    return None


def serving_bot_nick(irc_cmd: str) -> str | None:
    """IRC nick to preflight for a resolved download command (! line or PM bot)."""
    line = (irc_cmd or "").strip()
    if not line.startswith("!"):
        return None
    m = _COMMAND_RE.match(line)
    if not m:
        return None
    tag = m.group(1).lower()
    if tag in _PREFLIGHT_SKIP_TAGS:
        return None
    return tag


def adapt_download_command(target_id: str | None, command: str) -> str:
    """Map search-result commands to what the connected network's bots accept."""
    cid = normalize_channel_id(target_id)
    line = (command or "").strip()
    if cid != "undernet:bookz" or not line.startswith("!"):
        return line
    m = _COMMAND_RE.match(line)
    if not m:
        return line
    tag = m.group(1)
    tag_low = tag.lower()
    body = normalize_download_body(m.group(2))
    if tag_low in UNDERNET_LOCAL_TAGS:
        if tag_low == "get":
            return f"!get {body}"
        if tag_low == "oatmeal":
            return f"!Oatmeal {body}"
        return f"!{tag} {body}"
    if tag_low in UNDERNET_ON_CHANNEL_BOTS:
        return f"!{tag} {body}"
    # Foreign catalog tags from SearchBot (e.g. !Bsk, !Horla) → Oatmeal file line
    return f"!Oatmeal {body}"


def resolve_download_command(
    target_id: str | None,
    command: str,
    *,
    title: str | None = None,
    search_results: list[dict] | None = None,
    all_search_results: list[dict] | None = None,
) -> tuple[str, str | None, str | None]:
    """Return IRC command, optional feed hint, optional redirect target id."""
    line = (command or "").strip()
    cid = normalize_channel_id(target_id)
    pool = all_search_results or search_results
    if cid == "undernet:bookz" and pool:
        native = _find_native_network_row(pool, line, title)
        if native:
            cmd, redirect = native
            if redirect != cid:
                return (
                    cmd,
                    f"Undernet listing → fetch on {redirect}: {line} → {cmd}",
                    redirect,
                )
    if cid == "undernet:bookz" and search_results:
        get_cmd = _match_undernet_get(search_results, line, title)
        if get_cmd:
            if get_cmd.strip().lower() == line.lower():
                return get_cmd, None, None
            return get_cmd, f"Undernet: {line} → {get_cmd}", None
    adapted = adapt_download_command(target_id, line)
    if adapted != line:
        return adapted, f"Undernet: {line} → {adapted}", None
    return adapted, None, None