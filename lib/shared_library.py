"""Request-scoped access to another user’s kennel catalog."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from urllib.parse import quote

from . import library_shares
from . import user_paths


def owner_from_qs(qs: dict) -> str | None:
    raw = qs.get("owner")
    if raw is None:
        return None
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    cleaned = str(raw).strip()
    return cleaned or None


def owner_from_body(body: dict | None) -> str | None:
    if not body:
        return None
    cleaned = str(body.get("owner") or "").strip()
    return cleaned or None


def shared_storage_key(item_id: str, shared_owner: str | None) -> str:
    if shared_owner:
        return f"share:{shared_owner}:{item_id}"
    return item_id


def url_query_owner(shared_owner: str | None) -> str:
    if not shared_owner:
        return ""
    return "?owner=" + quote(shared_owner, safe="")


@contextmanager
def catalog_context(viewer: str, catalog_owner: str | None) -> Iterator[str | None]:
    if not catalog_owner:
        yield None
        return
    if not library_shares.can_read(viewer, catalog_owner):
        raise PermissionError("Shared kennel access denied")
    prev = user_paths.current_user_optional()
    user_paths.set_user(catalog_owner)
    try:
        yield catalog_owner
    finally:
        user_paths.set_user(prev)


def assert_own_catalog_only(catalog_owner: str | None, action: str = "modify") -> None:
    if catalog_owner:
        raise PermissionError(f"Cannot {action} another pup's kennel")