"""Custom kennel shelves API."""

from __future__ import annotations

from .. import shelves
from ..shared_library import assert_own_catalog_only, owner_from_qs
from ._types import RequestHandler


def _shelf_id_from_path(path: str, suffix: str = "") -> str | None:
    prefix = "/api/library/shelves/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if suffix and rest.endswith(suffix):
        rest = rest[: -len(suffix)]
    rest = rest.strip("/")
    if not rest or "/" in rest:
        return None
    return rest


def handle_get(handler: RequestHandler, path: str, qs: dict) -> bool:
    if path == "/api/library/shelves":
        shared = owner_from_qs(qs)
        assert_own_catalog_only(shared, "manage shelves on")
        handler.send_json(200, {"shelves": shelves.list_shelves()})
        return True
    return False


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path == "/api/library/shelves":
        assert_own_catalog_only(None, "manage shelves on")
        name = str(body.get("name") or "").strip()
        shelf = shelves.create_shelf(name)
        handler.send_json(201, {"ok": True, "shelf": shelf, "shelves": shelves.list_shelves()})
        return True
    return False


def handle_patch(handler: RequestHandler, path: str, body: dict) -> bool:
    shelf_id = _shelf_id_from_path(path)
    if shelf_id and path == f"/api/library/shelves/{shelf_id}":
        assert_own_catalog_only(None, "manage shelves on")
        if "name" not in body:
            raise ValueError("name required")
        shelf = shelves.rename_shelf(shelf_id, str(body.get("name") or ""))
        handler.send_json(200, {"ok": True, "shelf": shelf, "shelves": shelves.list_shelves()})
        return True
    return False


def handle_put(handler: RequestHandler, path: str, body: dict) -> bool:
    shelf_id = _shelf_id_from_path(path, "/items")
    if shelf_id and path == f"/api/library/shelves/{shelf_id}/items":
        assert_own_catalog_only(None, "manage shelves on")
        raw = body.get("item_ids")
        if not isinstance(raw, list):
            raise ValueError("item_ids must be a list")
        shelf = shelves.set_shelf_items(shelf_id, raw)
        handler.send_json(200, {"ok": True, "shelf": shelf, "shelves": shelves.list_shelves()})
        return True
    return False


def handle_delete(handler: RequestHandler, path: str, _qs: dict) -> bool:
    shelf_id = _shelf_id_from_path(path)
    if shelf_id and path == f"/api/library/shelves/{shelf_id}":
        assert_own_catalog_only(None, "manage shelves on")
        shelves.delete_shelf(shelf_id)
        handler.send_json(200, {"ok": True, "shelves": shelves.list_shelves()})
        return True
    return False