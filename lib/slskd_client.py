"""slskd REST client (Soulseek sidecar)."""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import threading
import uuid
from collections.abc import Callable
from typing import Any

from .core import DEFAULT_SLSKD_URL, SLSKD_MOCK, load_config, user_agent

DEFAULT_TIMEOUT = 45.0
POLL_INTERVAL = 0.75
DOWNLOAD_POLL_INTERVAL = 1.5
DOWNLOAD_TIMEOUT = 3600.0
SERVER_LOGIN_TIMEOUT = 45.0
SERVER_POLL_INTERVAL = 0.75

_jwt_lock = threading.Lock()
_jwt_token: str = ""
_jwt_expires: float = 0.0

_SUCCESS_STATES = frozenset(
    {"succeeded", "completed", "complete", "fulfilled", "finished"}
)
_FAIL_STATES = frozenset(
    {"failed", "errored", "error", "cancelled", "canceled", "rejected", "aborted"}
)


class SlskdError(Exception):
    """HTTP or API failure talking to slskd."""


class SlskdDisabledError(SlskdError):
    """Soulseek search disabled in config or env."""


def slskd_enabled() -> bool:
    if SLSKD_MOCK:
        return True
    cfg = load_config()
    if cfg.get("slskd_enabled") is False:
        return False
    env = os.environ.get("BOOKPUP_SLSKD_ENABLED", "").strip().lower()
    if env in ("0", "false", "no"):
        return False
    return True


def base_url() -> str:
    cfg = load_config()
    raw = (
        str(cfg.get("slskd_url") or os.environ.get("BOOKPUP_SLSKD_URL") or "")
        .strip()
    )
    if not raw:
        return DEFAULT_SLSKD_URL
    return raw.rstrip("/")


def api_key() -> str:
    env = os.environ.get("BOOKPUP_SLSKD_API_KEY", "").strip()
    if env:
        return env
    return str(load_config().get("slskd_api_key") or "").strip()


def login_credentials() -> tuple[str, str]:
    user = os.environ.get("BOOKPUP_SLSKD_USERNAME", "").strip()
    pw = os.environ.get("BOOKPUP_SLSKD_PASSWORD", "").strip()
    if not user or not pw:
        cfg = load_config()
        user = user or str(cfg.get("slskd_username") or "").strip()
        pw = pw or str(cfg.get("slskd_password") or "").strip()
    return user, pw


def _auth_configured() -> bool:
    if api_key():
        return True
    user, pw = login_credentials()
    return bool(user and pw)


def download_root() -> str:
    env = os.environ.get("BOOKPUP_SLSKD_DOWNLOAD_ROOT", "").strip()
    if env:
        return env
    return str(load_config().get("slskd_download_root") or "").strip()


def _timeout() -> float:
    try:
        return float(load_config().get("slskd_http_timeout") or DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT


def search_timeout_sec() -> int:
    try:
        return int(load_config().get("soulseek_search_timeout_sec") or 20)
    except (TypeError, ValueError):
        return 20


def search_timeout_ms() -> int:
    """slskd REST expects searchTimeout in milliseconds (not seconds)."""
    return max(1000, search_timeout_sec() * 1000)


def response_limit() -> int:
    try:
        return int(load_config().get("soulseek_response_limit") or 300)
    except (TypeError, ValueError):
        return 300


def get_server_state() -> dict[str, Any]:
    if SLSKD_MOCK:
        return {"isLoggedIn": True, "isConnected": True, "state": "LoggedIn"}
    payload = _request("GET", "/api/v0/server")
    if not isinstance(payload, dict):
        raise SlskdError("slskd server state missing")
    return payload


def _server_is_logged_in(state: dict[str, Any]) -> bool:
    if state.get("isLoggedIn") is True:
        return True
    label = str(state.get("state") or "").strip().lower().replace(" ", "")
    return label in ("loggedin", "connected,loggedin")


def connect_server() -> None:
    if SLSKD_MOCK:
        return
    _request("PUT", "/api/v0/server")


def ensure_server_ready(*, timeout: float = SERVER_LOGIN_TIMEOUT) -> None:
    """Ensure slskd is connected and logged in to the Soulseek network."""
    if SLSKD_MOCK:
        return
    deadline = time.monotonic() + max(5.0, float(timeout))
    reached_connect = False
    while time.monotonic() < deadline:
        state = get_server_state()
        if _server_is_logged_in(state):
            return
        transitioning = state.get("isTransitioning") is True or state.get(
            "isLoggingIn"
        ) is True or state.get("isConnecting") is True
        if not transitioning and not reached_connect:
            connect_server()
            reached_connect = True
        time.sleep(SERVER_POLL_INTERVAL)
    state = get_server_state()
    label = str(state.get("state") or "Disconnected")
    raise SlskdError(
        f"slskd Soulseek client not logged in (currently: {label}); try again"
    )


def _refresh_jwt() -> str:
    global _jwt_token, _jwt_expires
    user, pw = login_credentials()
    if not user or not pw:
        raise SlskdError("slskd login not configured")
    url = f"{base_url()}/api/v0/session"
    payload = json.dumps({"username": user, "password": pw}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": user_agent(),
        },
        method="POST",
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=_timeout(), context=ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    token = str(data.get("token") or "").strip()
    if not token:
        raise SlskdError("slskd session login failed")
    expires = data.get("expires")
    try:
        _jwt_expires = float(expires) if expires else time.time() + 3600
    except (TypeError, ValueError):
        _jwt_expires = time.time() + 3600
    _jwt_token = token
    return token


def _bearer_token() -> str:
    global _jwt_token, _jwt_expires
    with _jwt_lock:
        if _jwt_token and time.time() < _jwt_expires - 30:
            return _jwt_token
        return _refresh_jwt()


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | list[Any] | None = None,
    _retry_auth: bool = True,
) -> Any:
    if not slskd_enabled():
        raise SlskdDisabledError("Soulseek (slskd) is disabled")
    if not _auth_configured() and not SLSKD_MOCK:
        raise SlskdError("slskd credentials not configured (API key or username/password)")
    url = f"{base_url()}{path}"
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": user_agent(),
    }
    key = api_key()
    if key:
        headers["X-API-Key"] = key
    elif not SLSKD_MOCK:
        headers["Authorization"] = f"Bearer {_bearer_token()}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=_timeout(), context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            if not raw.strip():
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403) and _retry_auth and not key and not SLSKD_MOCK:
            with _jwt_lock:
                global _jwt_token
                _jwt_token = ""
            return _request(method, path, body=body, _retry_auth=False)
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
        except OSError:
            pass
        if exc.code == 409:
            detail_l = detail.lower()
            if "disconnected" in detail_l or "logged in" in detail_l:
                try:
                    connect_server()
                    ensure_server_ready()
                except SlskdError:
                    pass
                if _retry_auth:
                    return _request(method, path, body=body, _retry_auth=False)
        raise SlskdError(f"slskd HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SlskdError(f"slskd unreachable: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SlskdError("slskd returned invalid JSON") from exc


def _mock_search_payload(search_id: str, query: str) -> dict[str, Any]:
    from pathlib import Path

    fixture = (
        Path(__file__).resolve().parent.parent
        / "tests"
        / "fixtures"
        / "slskd_search_complete.json"
    )
    if fixture.is_file():
        data = json.loads(fixture.read_text())
        if isinstance(data, dict):
            data = dict(data)
            data["id"] = search_id
            data["searchText"] = query
            return data
    return {
        "id": search_id,
        "searchText": query,
        "isComplete": True,
        "responses": [],
    }


def start_search(query: str) -> str:
    q = (query or "").strip()
    if not q:
        raise ValueError("empty query")
    search_id = str(uuid.uuid4())
    if SLSKD_MOCK:
        return search_id
    ensure_server_ready()
    body = {
        "id": search_id,
        "searchText": q,
        "searchTimeout": search_timeout_ms(),
        "responseLimit": response_limit(),
        "filterResponses": True,
    }
    _request("POST", "/api/v0/searches", body=body)
    return search_id


def get_search(search_id: str, *, include_responses: bool = True) -> dict[str, Any]:
    sid = str(search_id or "").strip()
    if not sid:
        raise ValueError("search id required")
    if SLSKD_MOCK:
        return _mock_search_payload(sid, "")
    qs = "?includeResponses=true" if include_responses else ""
    payload = _request("GET", f"/api/v0/searches/{urllib.parse.quote(sid, safe='')}{qs}")
    if not isinstance(payload, dict):
        raise SlskdError("Search payload missing")
    return payload


def wait_search_complete(
    search_id: str,
    *,
    on_tick: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + search_timeout_sec() + 5.0
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = get_search(search_id)
        if last.get("isComplete") is True:
            return last
        state = str(last.get("state") or "").strip().lower()
        if state in ("completed", "complete", "timedout", "cancelled"):
            return last
        if on_tick:
            on_tick(last)
        time.sleep(POLL_INTERVAL)
    return last


def _iter_response_files(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    responses = payload.get("responses")
    if not isinstance(responses, list):
        return out
    for resp in responses:
        if not isinstance(resp, dict):
            continue
        username = str(resp.get("username") or resp.get("user") or "").strip()
        files = resp.get("files")
        if not isinstance(files, list):
            continue
        for f in files:
            if not isinstance(f, dict):
                continue
            filename = str(f.get("filename") or f.get("file") or "").strip()
            if not filename or not username:
                continue
            try:
                size = int(f.get("size") or f.get("length") or 0)
            except (TypeError, ValueError):
                size = 0
            out.append(
                {
                    "username": username,
                    "filename": filename,
                    "size": size,
                }
            )
    return out


def flatten_search(payload: dict[str, Any], *, search_id: str) -> list[dict[str, Any]]:
    sid = str(search_id or payload.get("id") or "").strip()
    rows: list[dict[str, Any]] = []
    for item in _iter_response_files(payload):
        rows.append({**item, "search_id": sid})
    limit = response_limit()
    if len(rows) > limit:
        rows = rows[:limit]
    return rows


def queue_download(username: str, filename: str, size: int) -> str:
    user = str(username or "").strip()
    fn = str(filename or "").strip()
    if not user or not fn:
        raise ValueError("username and filename required")
    body = [{"filename": fn, "size": int(size or 0)}]
    if SLSKD_MOCK:
        return "mock-transfer-1"
    ensure_server_ready()
    payload = _request(
        "POST",
        f"/api/v0/transfers/downloads/{urllib.parse.quote(user, safe='')}",
        body=body,
    )
    transfer_id = _extract_transfer_id(payload, user=user, filename=fn)
    if not transfer_id:
        raise SlskdError("slskd did not return a transfer id")
    return transfer_id


def _norm_filename(path: str) -> str:
    return str(path or "").replace("\\", "/").strip().casefold()


def _flatten_transfer_nodes(
    nodes: list[Any], *, username: str = ""
) -> list[dict[str, Any]]:
    """Expand slskd directory groupings into per-file transfer rows."""
    out: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        user = str(node.get("username") or node.get("user") or username or "").strip()
        nested_files = node.get("files")
        if isinstance(nested_files, list) and (
            node.get("directory") is not None or not node.get("id")
        ):
            for item in nested_files:
                if isinstance(item, dict):
                    row = dict(item)
                    row.setdefault("username", user)
                    out.append(row)
            continue
        if node.get("id") or node.get("filename"):
            row = dict(node)
            row.setdefault("username", user)
            out.append(row)
    return out


def _extract_transfer_id(payload: Any, *, user: str, filename: str) -> str:
    if isinstance(payload, dict):
        for key in ("id", "transferId", "transfer_id"):
            if payload.get(key):
                return str(payload[key])
        items = payload.get("transfers") or payload.get("downloads")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict) and first.get("id"):
                return str(first["id"])
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict) and first.get("id"):
            return str(first["id"])
    # slskd POST enqueue returns 201 with an empty body — poll until listed.
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        found = find_download_transfer(user, filename)
        if found and found.get("id"):
            return str(found["id"])
        time.sleep(0.35)
    return ""


def list_downloads() -> list[dict[str, Any]]:
    if SLSKD_MOCK:
        return []
    payload = _request("GET", "/api/v0/transfers/downloads")
    if isinstance(payload, list):
        out: list[dict[str, Any]] = []
        for group in payload:
            if not isinstance(group, dict):
                continue
            user = str(group.get("username") or group.get("user") or "").strip()
            transfers = group.get("directories") or group.get("transfers") or group.get("files")
            if isinstance(transfers, list):
                out.extend(_flatten_transfer_nodes(transfers, username=user))
        return out
    if isinstance(payload, dict):
        dirs = payload.get("directories")
        if isinstance(dirs, list):
            user = str(payload.get("username") or payload.get("user") or "").strip()
            return _flatten_transfer_nodes(dirs, username=user)
    return []


def get_download(username: str, transfer_id: str) -> dict[str, Any]:
    user = urllib.parse.quote(str(username or "").strip(), safe="")
    tid = urllib.parse.quote(str(transfer_id or "").strip(), safe="")
    if SLSKD_MOCK:
        return {
            "id": transfer_id,
            "state": "Succeeded",
            "filename": "Books/Mock/Title.epub",
            "size": 128,
        }
    payload = _request("GET", f"/api/v0/transfers/downloads/{user}/{tid}")
    if not isinstance(payload, dict):
        raise SlskdError("Download payload missing")
    return payload


def find_download_transfer(username: str, filename: str) -> dict[str, Any] | None:
    fn_key = _norm_filename(filename)
    user = str(username or "").strip()
    if not fn_key:
        return None
    for row in list_downloads():
        if user and str(row.get("username") or "").strip() != user:
            continue
        if _norm_filename(str(row.get("filename") or "")) == fn_key:
            return row
    return None


def _state_tokens(state: str) -> set[str]:
    s = str(state or "").strip().lower()
    return {part for part in s.replace(",", " ").split() if part}


def _state_ok(state: str) -> bool:
    tokens = _state_tokens(state)
    if tokens & _FAIL_STATES:
        return False
    return bool(tokens & _SUCCESS_STATES)


def _state_fail(state: str) -> bool:
    tokens = _state_tokens(state)
    if tokens & _FAIL_STATES:
        return True
    s = str(state or "").strip().lower()
    return s in _FAIL_STATES


def wait_download_complete(
    username: str,
    transfer_id: str,
    *,
    timeout: float = DOWNLOAD_TIMEOUT,
    on_tick: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = get_download(username, transfer_id)
        state = str(last.get("state") or last.get("status") or "")
        if _state_fail(state):
            raise SlskdError(f"slskd download failed: {state or 'unknown'}")
        if _state_ok(state):
            return last
        if on_tick:
            on_tick(last)
        time.sleep(DOWNLOAD_POLL_INTERVAL)
    raise SlskdError("slskd download timed out")


def health_probe() -> dict[str, Any]:
    out: dict[str, Any] = {
        "enabled": slskd_enabled(),
        "base_url": base_url(),
        "download_root_set": bool(download_root()),
    }
    if not out["enabled"]:
        out["reachable"] = False
        return out
    if SLSKD_MOCK:
        out["reachable"] = True
        return out
    if not _auth_configured():
        out["reachable"] = False
        out["error"] = "Credentials missing"
        return out
    try:
        _request("GET", "/api/v0/application")
        out["reachable"] = True
    except SlskdError as exc:
        out["reachable"] = False
        out["error"] = str(exc)[:120]
        return out
    try:
        state = get_server_state()
        out["server_logged_in"] = _server_is_logged_in(state)
        out["server_state"] = str(state.get("state") or "")[:40]
    except SlskdError as exc:
        out["server_logged_in"] = False
        out["server_state"] = ""
        out["server_error"] = str(exc)[:120]
    return out