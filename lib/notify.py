"""Optional push when a download job finishes (ntfy)."""

from __future__ import annotations

import json
import threading
import urllib.request
from typing import Any

from .core import load_config, public_base_url
from .url_safety import assert_ntfy_server_url


def _post_ntfy(server: str, topic: str, title: str, message: str) -> None:
    url = f"{server.rstrip('/')}/{topic}"
    body = json.dumps({"title": title, "message": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=8)  # noqa: S310


def maybe_job_done(job: dict[str, Any]) -> None:
    if str(job.get("type") or "") != "download":
        return
    if str(job.get("state") or "") != "done":
        return
    cfg = load_config()
    topic = str(cfg.get("ntfy_topic") or "").strip()
    if not topic:
        return
    try:
        server = assert_ntfy_server_url(str(cfg.get("ntfy_server") or "https://ntfy.sh"))
    except ValueError:
        return
    title = str(job.get("title") or "Book download")
    base = public_base_url(cfg)
    msg = f"Added to Fresh catches. Open BookPup: {base}"
    owner = str(job.get("owner") or "").strip()
    if owner:
        msg = f"For {owner}: {msg}"

    def run() -> None:
        try:
            _post_ntfy(server, topic, f"BookPup: {title[:80]}", msg[:400])
        except OSError:
            pass

    threading.Thread(target=run, daemon=True).start()


def maybe_sniff_watch_new(
    *,
    owner: str,
    watch_name: str,
    query: str,
    new_rows: list[dict],
) -> None:
    if not new_rows:
        return
    cfg = load_config()
    topic = str(cfg.get("ntfy_topic") or "").strip()
    if not topic:
        return
    try:
        server = assert_ntfy_server_url(str(cfg.get("ntfy_server") or "https://ntfy.sh"))
    except ValueError:
        return
    count = len(new_rows)
    label = watch_name[:60]
    title = f"BookPup: {count} new for “{label}”"
    lines = [f"Sniff: {query[:120]}"]
    if owner:
        lines.insert(0, f"For {owner}")
    for row in new_rows[:5]:
        t = str(row.get("title") or row.get("display") or "").strip()
        if t:
            lines.append(f"• {t[:100]}")
    if count > 5:
        lines.append(f"…and {count - 5} more")
    base = public_base_url(cfg)
    lines.append(f"Open BookPup: {base}")
    message = "\n".join(lines)[:900]

    def run() -> None:
        try:
            _post_ntfy(server, topic, title[:80], message)
        except OSError:
            pass

    threading.Thread(target=run, daemon=True).start()