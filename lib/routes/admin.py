"""Admin digest, backup, accounts."""

from __future__ import annotations

from .. import accounts, admin_digest, bugbot, library_export, quota, user_wipe
from ._types import RequestHandler


def handle_get(handler: RequestHandler, path: str, _qs: dict) -> bool:
    admin = handler._is_admin
    if path == "/api/admin/bug-inbox":
        if not admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True
        handler.send_json(200, {"reports": bugbot.list_inbox()})
        return True
    if path == "/api/admin/digest":
        if not admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True
        handler.send_json(200, admin_digest.build_digest())
        return True
    if path == "/api/admin/backup":
        if not admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True
        from datetime import date

        blob = library_export.admin_backup_zip()
        name = f"bookpup-backup-{date.today().isoformat()}.zip"
        handler.send_bytes(blob, "application/zip", name)
        return True
    if path == "/api/admin/accounts":
        if not admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True
        rows = []
        for row in accounts.list_users():
            u = str(row.get("username") or "")
            rows.append(accounts.public_row(row, quota.library_usage_for(u)["used_bytes"]))
        handler.send_json(200, {"accounts": rows})
        return True
    if path.startswith("/api/admin/accounts/") and path.endswith("/wipe-preview"):
        if not admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True
        name = path[len("/api/admin/accounts/") : -len("/wipe-preview")].strip("/")
        if not name or "/" in name:
            raise ValueError("Invalid account name")
        data = user_wipe.wipe_preview(handler._current_user, name)
        handler.send_json(200, data)
        return True
    return False


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path == "/api/admin/accounts":
        if not handler._is_admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True
        username = str(body.get("username") or "").strip()
        password = str(body.get("password") or "")
        quota_b = body.get("quota_bytes")
        admin_flag = bool(body.get("admin"))
        row = accounts.create_user(
            username,
            password,
            quota_bytes=int(quota_b) if quota_b is not None else None,
            admin=admin_flag,
        )
        handler.send_json(201, {"ok": True, "account": row})
        return True
    if path.startswith("/api/admin/accounts/") and path.endswith("/wipe"):
        if not handler._is_admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True
        account_name = path[len("/api/admin/accounts/") : -len("/wipe")].strip("/")
        if not account_name or "/" in account_name:
            raise ValueError("Invalid account name")

        def run_wipe() -> None:
            wiped = user_wipe.wipe_account(
                handler._current_user,
                target=account_name,
                current_password=str(body.get("current_password") or ""),
                phrase=str(body.get("phrase") or ""),
            )
            handler.send_json(200, {"ok": True, "target": wiped})

        handler.dispatch(run_wipe)
        return True
    if path.startswith("/api/admin/accounts/"):
        if not handler._is_admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True
        account_name = path[len("/api/admin/accounts/") :]
        if not account_name or "/" in account_name:
            raise ValueError("Invalid account name")
        updated = accounts.update_user(account_name, body)
        handler.send_json(200, {"ok": True, "account": updated})
        return True
    return False


def handle_delete(handler: RequestHandler, path: str, qs: dict | None = None) -> bool:
    prefix = "/api/admin/bug-inbox/"
    if path.startswith(prefix):
        if not handler._is_admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True
        rest = path[len(prefix) :].strip()
        if not rest or "/" in rest:
            handler.send_json(400, {"error": "Invalid report id"})
            return True
        try:
            report_id = int(rest)
        except ValueError:
            handler.send_json(400, {"error": "Invalid report id"})
            return True

        def drop() -> None:
            try:
                bugbot.dismiss_report(report_id)
            except KeyError:
                handler.send_json(404, {"error": "Report not found"})
                return
            handler.send_json(200, {"ok": True})

        handler.dispatch(drop)
        return True
    if not path.startswith("/api/admin/accounts/"):
        return False
    if not handler._is_admin:
        handler.send_json(403, {"error": "Admin access required"})
        return True
    name = path[len("/api/admin/accounts/") :]

    def drop_account() -> None:
        accounts.delete_user(name)
        handler.send_json(200, {"ok": True})

    handler.dispatch(drop_account)
    return True