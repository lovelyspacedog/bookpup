"""Per-user IRC search draft and saved result sets."""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Any

from . import jobs
from . import user_paths

MAX_SAVED = 25
MAX_ROWS = 2500
MAX_NAME_LEN = 80
MAX_FILE_BYTES = 4_000_000


def _path(username: str | None = None) -> Path:
    return user_paths.user_root(username) / "search_workspace.json"


def _empty_draft() -> dict[str, Any]:
    return {
        "query": "",
        "channel": "irchighway:ebooks",
        "filter": "",
        "results": [],
        "job_id": None,
        "updated_at": 0.0,
    }


def _load_raw(username: str | None = None) -> dict[str, Any]:
    path = _path(username)
    if not path.is_file():
        return {"draft": _empty_draft(), "saved": []}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"draft": _empty_draft(), "saved": []}
    if not isinstance(data, dict):
        return {"draft": _empty_draft(), "saved": []}
    draft = data.get("draft")
    saved = data.get("saved")
    if not isinstance(draft, dict):
        draft = _empty_draft()
    if not isinstance(saved, list):
        saved = []
    return {"draft": draft, "saved": saved}


def _write(data: dict[str, Any], username: str | None = None) -> None:
    user_paths.ensure_user_dirs(user_paths.current_user() if username is None else username)
    path = _path(username)
    text = json.dumps(data, indent=2) + "\n"
    if len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("Search workspace too large; remove some saved searches")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def sanitize_results(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in rows[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        cmd = str(raw.get("command") or "").strip()
        is_xdcc = raw.get("download_kind") == "xdcc" or isinstance(raw.get("xdcc"), dict)
        if not is_xdcc and not cmd.startswith("!"):
            continue
        entry: dict[str, Any] = {
            "server": str(raw.get("server") or ""),
            "title": str(raw.get("title") or ""),
            "command": cmd or (f"!xdcc #{raw.get('xdcc', {}).get('slot', '')}" if is_xdcc else ""),
            "display": str(raw.get("display") or cmd or raw.get("title") or ""),
        }
        if is_xdcc:
            entry["download_kind"] = "xdcc"
            if isinstance(raw.get("xdcc"), dict):
                entry["xdcc"] = raw.get("xdcc")
        if raw.get("size_hint") is not None:
            entry["size_hint"] = str(raw.get("size_hint"))
        if raw.get("irc_target"):
            entry["irc_target"] = str(raw.get("irc_target"))
        if raw.get("network"):
            entry["network"] = str(raw.get("network"))
        out.append(entry)
    return out


def _job_usable(job_id: str | None, owner: str) -> bool:
    if not job_id:
        return False
    try:
        job = jobs.load_job(str(job_id))
    except KeyError:
        return False
    if str(job.get("owner") or "") != owner:
        return False
    if job.get("type") != "search":
        return False
    results = job.get("results")
    return isinstance(results, list) and len(results) > 0


def ensure_fetch_job(
    owner: str,
    query: str,
    channel: str,
    results: list[dict[str, Any]],
    job_id: str | None,
) -> str:
    if _job_usable(job_id, owner):
        return str(job_id)
    job = jobs.create_job(
        "search",
        query=str(query or "").strip() or "(saved)",
        channel=str(channel or "irchighway:ebooks"),
        owner=owner,
        state="done",
        results=results,
        result_count=len(results),
    )
    return str(job["id"])


def get_workspace() -> dict[str, Any]:
    data = _load_raw()
    draft = data["draft"]
    draft["results"] = sanitize_results(draft.get("results"))
    saved = []
    for item in data["saved"]:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        saved.append(
            {
                "id": str(item["id"]),
                "name": str(item.get("name") or "Untitled")[:MAX_NAME_LEN],
                "query": str(item.get("query") or ""),
                "channel": str(item.get("channel") or ""),
                "filter": str(item.get("filter") or ""),
                "result_count": len(sanitize_results(item.get("results"))),
                "saved_at": float(item.get("saved_at") or 0),
            }
        )
    return {
        "draft": {
            "query": str(draft.get("query") or ""),
            "channel": str(draft.get("channel") or "irchighway:ebooks"),
            "filter": str(draft.get("filter") or ""),
            "results": draft["results"],
            "job_id": draft.get("job_id"),
            "updated_at": float(draft.get("updated_at") or 0),
            "result_count": len(draft["results"]),
        },
        "saved": saved,
        "limits": {
            "max_saved": MAX_SAVED,
            "max_rows": MAX_ROWS,
        },
    }


def update_draft(body: dict[str, Any]) -> dict[str, Any]:
    owner = user_paths.current_user()
    data = _load_raw()
    draft = data.get("draft") if isinstance(data.get("draft"), dict) else _empty_draft()
    if "query" in body:
        draft["query"] = str(body.get("query") or "").strip()
    if "channel" in body:
        draft["channel"] = str(body.get("channel") or "").strip() or "irchighway:ebooks"
    if "filter" in body:
        draft["filter"] = str(body.get("filter") or "")[:200]
    if "results" in body:
        results = sanitize_results(body.get("results"))
        draft["results"] = results
        job_id = body.get("job_id")
        draft["job_id"] = ensure_fetch_job(
            owner,
            str(draft.get("query") or ""),
            str(draft.get("channel") or ""),
            results,
            str(job_id) if job_id else draft.get("job_id"),
        )
    elif "job_id" in body and draft.get("results"):
        draft["job_id"] = ensure_fetch_job(
            owner,
            str(draft.get("query") or ""),
            str(draft.get("channel") or ""),
            sanitize_results(draft.get("results")),
            str(body.get("job_id") or "") or None,
        )
    draft["updated_at"] = time.time()
    data["draft"] = draft
    _write(data)
    ws = get_workspace()
    ws["draft"]["job_id"] = draft.get("job_id")
    return ws["draft"]


def save_draft_as(name: str) -> dict[str, Any]:
    label = str(name or "").strip()
    if not label:
        raise ValueError("name required")
    if len(label) > MAX_NAME_LEN:
        raise ValueError(f"name must be at most {MAX_NAME_LEN} characters")
    data = _load_raw()
    draft = data.get("draft") if isinstance(data.get("draft"), dict) else _empty_draft()
    results = sanitize_results(draft.get("results"))
    if not results:
        raise ValueError("Draft has no results to save")
    saved = data.get("saved") if isinstance(data.get("saved"), list) else []
    if len(saved) >= MAX_SAVED:
        raise ValueError(f"At most {MAX_SAVED} saved searches; remove one first")
    owner = user_paths.current_user()
    job_id = ensure_fetch_job(
        owner,
        str(draft.get("query") or ""),
        str(draft.get("channel") or ""),
        results,
        draft.get("job_id"),
    )
    entry = {
        "id": secrets.token_urlsafe(10),
        "name": label,
        "query": str(draft.get("query") or ""),
        "channel": str(draft.get("channel") or ""),
        "filter": str(draft.get("filter") or ""),
        "results": results,
        "job_id": job_id,
        "saved_at": time.time(),
    }
    saved.append(entry)
    data["saved"] = saved
    if isinstance(data.get("draft"), dict):
        data["draft"]["job_id"] = job_id
    _write(data)
    return {"id": entry["id"], "name": label, "workspace": get_workspace()}


def load_saved(saved_id: str) -> dict[str, Any]:
    sid = str(saved_id or "").strip()
    if not sid:
        raise ValueError("id required")
    data = _load_raw()
    saved = data.get("saved") if isinstance(data.get("saved"), list) else []
    match = None
    for item in saved:
        if isinstance(item, dict) and str(item.get("id")) == sid:
            match = item
            break
    if not match:
        raise KeyError(saved_id)
    owner = user_paths.current_user()
    results = sanitize_results(match.get("results"))
    job_id = ensure_fetch_job(
        owner,
        str(match.get("query") or ""),
        str(match.get("channel") or ""),
        results,
        match.get("job_id"),
    )
    data["draft"] = {
        "query": str(match.get("query") or ""),
        "channel": str(match.get("channel") or ""),
        "filter": str(match.get("filter") or ""),
        "results": results,
        "job_id": job_id,
        "updated_at": time.time(),
    }
    match["job_id"] = job_id
    _write(data)
    draft = get_workspace()["draft"]
    draft["job_id"] = job_id
    return draft


def delete_saved(saved_id: str) -> dict[str, Any]:
    sid = str(saved_id or "").strip()
    data = _load_raw()
    saved = data.get("saved") if isinstance(data.get("saved"), list) else []
    nxt = [x for x in saved if isinstance(x, dict) and str(x.get("id")) != sid]
    if len(nxt) == len(saved):
        raise KeyError(saved_id)
    data["saved"] = nxt
    _write(data)
    return get_workspace()


def reorder_saved(order: list[str]) -> dict[str, Any]:
    if not isinstance(order, list) or not order:
        raise ValueError("order required")
    data = _load_raw()
    saved = data.get("saved") if isinstance(data.get("saved"), list) else []
    by_id = {str(x.get("id")): x for x in saved if isinstance(x, dict) and x.get("id")}
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for raw_id in order:
        sid = str(raw_id or "").strip()
        if not sid or sid in seen:
            continue
        item = by_id.get(sid)
        if item:
            ordered.append(item)
            seen.add(sid)
    for item in saved:
        sid = str(item.get("id") or "")
        if sid and sid not in seen and isinstance(item, dict):
            ordered.append(item)
    data["saved"] = ordered
    _write(data)
    return get_workspace()