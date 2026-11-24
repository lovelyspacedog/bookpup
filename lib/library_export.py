"""Library catalog export and admin config backup."""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path
from typing import Any

from . import accounts
from . import core
from . import library
from . import user_paths
from .core import VERSION


def export_user_catalog() -> dict[str, Any]:
    items = []
    for row in library.list_items():
        slim = {k: v for k, v in row.items() if k not in ("staging_id",)}
        items.append(slim)
    return {
        "bookpup_export": 1,
        "version": VERSION,
        "exported_at": time.time(),
        "username": user_paths.current_user(),
        "items": items,
    }


def admin_backup_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        cfg = core.CONFIG_FILE
        if cfg.is_file():
            zf.writestr("config.json", cfg.read_bytes())
        acct_path = core.CONFIG_DIR / "accounts.json"
        if acct_path.is_file():
            data = json.loads(acct_path.read_text())
            for row in data.get("users") or []:
                if isinstance(row, dict) and "password" in row:
                    row["password"] = "***"
            zf.writestr("accounts.redacted.json", json.dumps(data, indent=2).encode())
        for row in accounts.list_users():
            u = str(row.get("username") or "")
            if not u:
                continue
            prefix = f"users/{u}/"
            for name in ("library.json", "reading.json", "search_workspace.json"):
                path = user_paths.user_root(u) / name
                if path.is_file():
                    zf.writestr(prefix + name, path.read_bytes())
    return buf.getvalue()