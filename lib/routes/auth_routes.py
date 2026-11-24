"""Login, logout, account."""

from __future__ import annotations

from .. import accounts, auth, user_wipe
from ._types import RequestHandler


def handle_get(handler: RequestHandler, path: str, _qs: dict) -> bool:
    if path == "/api/account/wipe-preview":
        data = user_wipe.wipe_preview(handler._current_user, handler._current_user)
        handler.send_json(200, data)
        return True
    return False


def route_login(handler: RequestHandler, length: int) -> None:
    from ..login_limit import check_allowed, record_failure, record_success

    client_ip = handler.client_address[0] if handler.client_address else None
    allowed, retry_after = check_allowed(client_ip)
    if not allowed:
        handler.send_json(
            429,
            {
                "error": "Too many sign-in attempts. Try again later.",
                "retry_after_seconds": retry_after,
            },
        )
        return
    body = handler.read_json(length)
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not username or not password:
        raise ValueError("username and password required")
    if not auth.verify_credentials(username, password):
        record_failure(client_ip)
        handler.send_json(401, {"error": "Invalid username or password"})
        return
    record_success(client_ip)
    accounts.migrate_legacy()
    token = auth.create_token(username)
    handler.send_json(
        200,
        {
            "ok": True,
            "token": token,
            "username": username,
            "admin": accounts.is_admin(username),
        },
    )


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path == "/api/account":
        current_pw = str(body.get("current_password") or "")
        new_name = str(body.get("new_username") or "").strip() or None
        new_pw = str(body.get("new_password") or "") or None
        final = accounts.change_own_login(
            handler._current_user,
            current_password=current_pw,
            new_username=new_name,
            new_password=new_pw,
        )
        header = handler.headers.get("Authorization") or ""
        token = header[7:].strip() if header.startswith("Bearer ") else ""
        if token:
            auth.set_session_username(token, final)
        handler.send_json(
            200,
            {
                "ok": True,
                "username": final,
                "admin": accounts.is_admin(final),
            },
        )
        return True
    if path == "/api/account/wipe":
        user_wipe.wipe_account(
            handler._current_user,
            current_password=str(body.get("current_password") or ""),
            phrase=str(body.get("phrase") or ""),
        )
        handler.send_json(200, {"ok": True})
        return True
    if path == "/api/logout":
        header = handler.headers.get("Authorization") or ""
        if header.startswith("Bearer "):
            auth.revoke_token(header[7:].strip())
        handler.send_json(200, {"ok": True})
        return True
    return False