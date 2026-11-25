"""Admin inbox for failed fetch (download) jobs — IRC feed + job details as markdown."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any

from . import core, irc_feed, json_atomic

INBOX_FILE = core.CONFIG_DIR / "fetch_fail_inbox.json"
MAX_INBOX = 150

_lock = threading.Lock()
_loaded = False
_entries: list[dict[str, Any]] = []
_next_id = 1


def _load_unlocked() -> None:
    global _loaded, _entries, _next_id
    _entries = []
    _next_id = 1
    if INBOX_FILE.is_file():
        try:
            raw = json.loads(INBOX_FILE.read_text())
            if isinstance(raw, dict):
                rows = raw.get("entries")
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        eid = int(row.get("id") or 0)
                        if eid < 1:
                            continue
                        _entries.append(dict(row))
                _next_id = max(_next_id, int(raw.get("next_id") or 1))
                if _entries:
                    _next_id = max(_next_id, max(int(e["id"]) for e in _entries) + 1)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    _loaded = True


def _persist_unlocked() -> None:
    core.ensure_dirs()
    json_atomic.atomic_write_json(
        INBOX_FILE,
        {"version": 1, "next_id": _next_id, "entries": list(_entries)},
    )


def _ensure() -> None:
    with _lock:
        if not _loaded:
            _load_unlocked()


def _fmt_ts(ts: float) -> str:
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (OSError, OverflowError, ValueError):
        return str(ts)


def _feed_lines(job: dict[str, Any]) -> list[dict[str, Any]]:
    owner = str(job.get("owner") or "").strip() or None
    since_id = job.get("feed_seq_start")
    since_ts = float(job.get("created_at") or 0)
    try:
        sid = int(since_id) if since_id is not None else 0
    except (TypeError, ValueError):
        sid = 0
    return irc_feed.events_for_failure(owner=owner, since_id=sid, since_ts=since_ts)


def build_markdown(job: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Fetch failure log",
        "",
        f"- **Job id:** `{job.get('id', '')}`",
        f"- **Pup:** {job.get('owner') or '(none)'}",
        f"- **When:** {_fmt_ts(float(job.get('updated_at') or job.get('created_at') or 0))}",
        f"- **Error:** {job.get('error') or '(none)'}",
        "",
        "## Request",
        "",
    ]
    for key in (
        "title",
        "channel",
        "command",
        "download_kind",
        "query",
        "irc_status",
    ):
        if job.get(key):
            lines.append(f"- **{key}:** `{job[key]}`")
    xdcc = job.get("xdcc")
    if isinstance(xdcc, dict) and xdcc:
        lines.append(f"- **xdcc:** `{json.dumps(xdcc, ensure_ascii=False)[:400]}`")
    sk = job.get("soulseek")
    if isinstance(sk, dict) and sk:
        lines.append(f"- **soulseek:** `{json.dumps(sk, ensure_ascii=False)[:400]}`")
    attempts = job.get("fetch_fallback_attempts")
    if attempts:
        lines.append(f"- **fetch_fallback_attempts:** {len(attempts)}")
    if job.get("gutenberg_fallback"):
        lines.append("- **gutenberg_fallback:** attempted")
    lines.extend(["", "## Den chatter (IRC / session feed)", ""])
    feed = _feed_lines(job)
    if not feed:
        lines.append("_No feed lines captured for this job window._")
    else:
        for ev in feed:
            ts = _fmt_ts(float(ev.get("ts") or 0))
            direction = str(ev.get("dir") or "?")
            kind = str(ev.get("kind") or "")
            target = str(ev.get("target") or "").strip()
            text = str(ev.get("text") or "")
            prefix = f"`{ts}`"
            if target:
                prefix += f" **{direction}** → `{target}`"
            else:
                prefix += f" **{direction}**"
            if kind and kind not in ("privmsg", "session"):
                prefix += f" ({kind})"
            lines.append(f"- {prefix}: {text}")
    lines.append("")
    return "\n".join(lines)


def record_failed_download(job: dict[str, Any]) -> int | None:
    """Persist a failed download report for admins. Returns inbox id or None."""
    if str(job.get("type") or "") != "download":
        return None
    if str(job.get("state") or "") != "error":
        return None
    err = str(job.get("error") or "").strip()
    if not err:
        return None
    _ensure()
    now = time.time()
    markdown = build_markdown(job)
    global _next_id
    with _lock:
        job_id = str(job.get("id") or "")
        for row in _entries:
            if str(row.get("job_id") or "") == job_id and str(row.get("error") or "") == err:
                return int(row["id"])
        eid = _next_id
        _next_id += 1
        _entries.append(
            {
                "id": eid,
                "job_id": job_id,
                "from": str(job.get("owner") or "").strip() or "?",
                "title": str(job.get("title") or job.get("command") or "Fetch")[:160],
                "error": err[:240],
                "ts": now,
                "markdown": markdown,
            }
        )
        while len(_entries) > MAX_INBOX:
            _entries.pop(0)
        _persist_unlocked()
        return eid


def list_inbox() -> list[dict[str, Any]]:
    _ensure()
    with _lock:
        out = []
        for row in _entries:
            out.append(
                {
                    "id": row["id"],
                    "job_id": row.get("job_id"),
                    "from": row.get("from"),
                    "title": row.get("title"),
                    "error": row.get("error"),
                    "ts": row.get("ts"),
                }
            )
        return sorted(out, key=lambda r: float(r.get("ts") or 0), reverse=True)


def get_markdown(entry_id: int) -> str:
    _ensure()
    with _lock:
        for row in _entries:
            if int(row["id"]) == int(entry_id):
                md = row.get("markdown")
                if isinstance(md, str) and md.strip():
                    return md
                raise KeyError(str(entry_id))
        raise KeyError(str(entry_id))


def dismiss_entry(entry_id: int) -> None:
    _ensure()
    with _lock:
        idx = next(
            (i for i, r in enumerate(_entries) if int(r["id"]) == int(entry_id)),
            None,
        )
        if idx is None:
            raise KeyError(str(entry_id))
        _entries.pop(idx)
        _persist_unlocked()