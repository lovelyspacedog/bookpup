"""Library catalog, uploads, metadata, reading."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from .. import (
    calibre_import,
    cover_search,
    covers as covers_mod,
    library,
    library_export,
    metadata_search,
    reading,
    reader_ai,
    transfer,
)
from ..comic import comic_module
from ..comic_errors import ComicReadError
from .. import device_delivery, kindle_smtp, sideload_tokens
from .. import accounts
from ..convert import prepare_view
from ..core import public_base_url
from ..import_session import create_session, finish_session, write_chunk
from ..shared_library import (
    assert_own_catalog_only,
    catalog_context,
    owner_from_body,
    owner_from_qs,
    url_query_owner,
)
from ..upload import read_multipart_upload, save_multipart_files
from ._types import RequestHandler

_IMPORT_SESSION_PREFIXES = (
    "/api/library/import-calibre/session/",
    "/api/library/koreader/import/session/",
)


def _with_item_catalog(handler: RequestHandler, qs: dict, fn):
    shared = owner_from_qs(qs)
    with catalog_context(handler._current_user, shared):
        return fn()


def handle_get(handler: RequestHandler, path: str, qs: dict) -> bool:
    owner = handler._current_user
    if path.startswith("/api/library/shares"):
        return False
    shared = owner_from_qs(qs)
    if path == "/api/library/export":
        assert_own_catalog_only(shared, "export")
        payload = library_export.export_user_catalog()
        import json as _json

        body = _json.dumps(payload, indent=2).encode()
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in owner)
        handler.send_bytes(body, "application/json; charset=utf-8", f"bookpup-catalog-{safe}.json")
        return True
    if path == "/api/library":
        with catalog_context(handler._current_user, shared):
            payload = library.status()
        if shared:
            payload["shared"] = True
            payload["owner"] = shared
        handler.send_json(200, payload)
        return True
    if not path.startswith("/api/library/"):
        return False
    segments = [p for p in path.split("/") if p]
    if len(segments) == 4 and segments[3] == "cover":
        item_id = segments[2]

        def serve_cover() -> None:
            cover = covers_mod.resolve_cover_path(item_id)
            if cover is None or not cover.is_file():
                handler.send_json(404, {"error": "No cover"})
                return
            handler.send_bytes(cover.read_bytes(), covers_mod.cover_mime(cover), None)

        _with_item_catalog(handler, qs, serve_cover)
        return True
    if len(segments) == 5 and segments[3] == "ai" and segments[4] == "status":
        assert_own_catalog_only(shared, "use Study on")
        item_id = segments[2]

        def ai_status() -> None:
            library.item_path(item_id)
            handler.send_json(200, reader_ai.status())

        _with_item_catalog(handler, qs, ai_status)
        return True
    if len(segments) == 4 and segments[3] == "reading":
        item_id = segments[2]
        if shared:
            from .. import library_shares

            if not library_shares.can_read(handler._current_user, shared):
                raise PermissionError("Shared kennel access denied")
            from .. import user_paths

            user_paths.set_user(shared)
            try:
                library.item_path(item_id)
            finally:
                user_paths.set_user(handler._current_user)
            handler.send_json(200, reading.get_state(item_id, shared_owner=shared))
        else:
            library.item_path(item_id)
            handler.send_json(200, reading.get_state(item_id))
        return True
    if len(segments) >= 5 and segments[3] == "comic":
        item_id = segments[2]

        def comic_route() -> None:
            file_path = library.item_path(item_id)
            if len(segments) == 5 and segments[4] == "meta":
                mod = comic_module(file_path)
                try:
                    handler.send_json(200, mod.comic_meta(file_path))
                except ComicReadError as exc:
                    handler.send_json(
                        422,
                        {"error": str(exc), "debug_stderr": exc.debug_stderr},
                    )
                return
            if len(segments) == 6 and segments[4] == "page":
                try:
                    page_ix = int(segments[5])
                except ValueError as exc:
                    raise ValueError("Invalid page") from exc
                mod = comic_module(file_path)
                try:
                    data, mime = mod.page_bytes(file_path, page_ix)
                except ComicReadError as exc:
                    handler.send_json(
                        422,
                        {"error": str(exc), "debug_stderr": exc.debug_stderr},
                    )
                    return
                handler.send_bytes(data, mime)

        _with_item_catalog(handler, qs, comic_route)
        return True
    if len(segments) == 4 and segments[3] == "sideload":
        item_id = segments[2]
        assert_own_catalog_only(shared, "send books to an e-reader from")

        def sideload_formats() -> None:
            row = library.get_item_row(item_id)
            if not library.is_registered(row):
                raise ValueError("Only catalogued bones can be sent to an e-reader")
            library.item_path(item_id)
            handler.send_json(
                200,
                {
                    "ok": True,
                    "item_id": item_id,
                    "title": row.get("title") or row.get("filename"),
                    "formats": device_delivery.delivery_options(item_id),
                    "ttl_seconds": sideload_tokens.DEFAULT_TTL_SECONDS,
                },
            )

        _with_item_catalog(handler, qs, sideload_formats)
        return True
    if len(segments) == 4 and segments[3] == "read":
        item_id = segments[2]
        if not item_id:
            raise ValueError("Invalid library id")

        def serve_read() -> None:
            meta = prepare_view(item_id)
            file_path = Path(meta["path"])
            view_fmt = meta["format"]
            ctype = {
                "pdf": "application/pdf",
                "epub": "application/epub+zip",
                "txt": "text/plain; charset=utf-8",
                "md": "text/markdown; charset=utf-8",
                "html": "text/html; charset=utf-8",
                "cbz": "application/vnd.comicbook+zip",
                "cbr": "application/vnd.comicbook-rar",
            }.get(view_fmt) or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            handler.send_bytes(file_path.read_bytes(), ctype)

        _with_item_catalog(handler, qs, serve_read)
        return True
    if len(segments) == 3:
        item_id = segments[2]

        def serve_file() -> None:
            file_path = library.item_path(item_id)
            ctype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            handler.send_bytes(file_path.read_bytes(), ctype, file_path.name)

        _with_item_catalog(handler, qs, serve_file)
        return True
    return False


def _import_session_id(path: str, suffix: str) -> str:
    for prefix in _IMPORT_SESSION_PREFIXES:
        if path.startswith(prefix) and path.endswith(suffix):
            return path[len(prefix) : -len(suffix)]
    raise ValueError("Invalid import session path")


def try_post_early(handler: RequestHandler, path: str, length: int) -> bool:
    """Multipart and import session paths handled in do_POST before JSON body."""
    if path == "/api/library/import-calibre":
        handler.dispatch(lambda: route_import_calibre(handler, length))
        return True
    if path == "/api/library/import-calibre/session":
        handler.dispatch(lambda: route_import_session_create(handler, length))
        return True
    if path.startswith("/api/library/import-calibre/session/") and path.endswith("/chunk"):
        handler.dispatch(lambda: route_import_chunk(handler, path, length))
        return True
    if path.startswith("/api/library/import-calibre/session/") and path.endswith("/finish"):
        handler.dispatch(lambda: route_import_finish(handler, path, length))
        return True
    if path == "/api/library/upload":
        ctype = handler.headers.get("Content-Type") or ""
        if "multipart/form-data" not in ctype:
            handler.send_json(400, {"error": "Expected multipart/form-data upload"})
            return True
        handler.dispatch(lambda: route_library_upload(handler, length, ctype))
        return True
    if path == "/api/library/koreader/import/session":
        handler.dispatch(lambda: route_koreader_session_create(handler, length))
        return True
    if path.startswith("/api/library/koreader/import/session/") and path.endswith("/chunk"):
        handler.dispatch(lambda: route_import_chunk(handler, path, length))
        return True
    if path.startswith("/api/library/koreader/import/session/") and path.endswith("/finish"):
        handler.dispatch(lambda: route_import_finish(handler, path, length))
        return True
    if path.startswith("/api/library/") and path.endswith("/cover"):
        ctype = handler.headers.get("Content-Type") or ""
        if "multipart/form-data" in ctype:
            handler.dispatch(lambda: route_upload_cover(handler, path, length, ctype))
            return True
    return False


def route_library_upload(handler: RequestHandler, length: int, content_type: str) -> None:
    body_path = handler.spool_body(length)
    uploaded: list[Path] = []
    upload_dir: Path | None = None
    try:
        uploaded = save_multipart_files(body_path, content_type)
        if not uploaded:
            raise ValueError("No file in upload")
        if len(uploaded) > 1:
            raise ValueError("Upload one file at a time")
        pick = uploaded[0]
        data = pick.read_bytes()
        title = pick.stem
        item = library.add_upload(data, pick.name, title_hint=title)
        handler.send_json(201, {"item": item, "library": library.status()})
    finally:
        body_path.unlink(missing_ok=True)
        for path in uploaded:
            path.unlink(missing_ok=True)
        if upload_dir is not None:
            try:
                upload_dir.rmdir()
            except OSError:
                pass


def route_import_calibre(handler: RequestHandler, length: int) -> None:
    ctype = handler.headers.get("Content-Type") or ""
    if "multipart/form-data" not in ctype:
        raise ValueError("Expected multipart/form-data upload")
    body_path = handler.spool_body(length)
    uploaded: list[Path] = []
    upload_dir: Path | None = None
    try:
        uploaded = save_multipart_files(body_path, ctype)
        if uploaded:
            upload_dir = uploaded[0].parent
        result = calibre_import.import_parts(uploaded)
        handler.send_json(200, result)
    finally:
        body_path.unlink(missing_ok=True)
        for path in uploaded:
            path.unlink(missing_ok=True)
        if upload_dir is not None:
            try:
                upload_dir.rmdir()
            except OSError:
                pass


def route_import_session_create(handler: RequestHandler, length: int) -> None:
    body = handler.read_json(length)
    parts = body.get("parts")
    if not isinstance(parts, list):
        raise ValueError("parts array required")
    handler.send_json(201, create_session(parts, kind="calibre"))


def route_koreader_session_create(handler: RequestHandler, length: int) -> None:
    body = handler.read_json(length)
    parts = body.get("parts")
    if not isinstance(parts, list):
        raise ValueError("parts array required")
    handler.send_json(201, create_session(parts, kind="koreader"))


def route_import_chunk(handler: RequestHandler, path: str, length: int) -> None:
    from ..import_session import CHUNK_SIZE

    if length <= 0:
        raise ValueError("Empty chunk")
    if length > CHUNK_SIZE + 8192:
        raise ValueError("Chunk too large")
    part_name = str(handler.headers.get("X-Bookpup-Part") or "").strip()
    if not part_name:
        raise ValueError("X-Bookpup-Part required")
    try:
        offset = int(handler.headers.get("X-Bookpup-Offset") or "")
    except ValueError:
        raise ValueError("X-Bookpup-Offset required")
    session_id = _import_session_id(path, "/chunk")
    data = handler.rfile.read(length)
    if len(data) != length:
        raise ValueError("Short chunk body")
    handler.send_json(200, write_chunk(session_id, part_name, offset, data))


def route_import_finish(handler: RequestHandler, path: str, length: int) -> None:
    if length > 4096:
        handler.rfile.read(length)
    else:
        _ = handler.read_json(length)
    session_id = _import_session_id(path, "/finish")
    result = finish_session(session_id)
    if isinstance(result, dict) and "library" not in result:
        result["library"] = library.status()
    handler.send_json(200, result)


def route_upload_cover(handler: RequestHandler, path: str, length: int, content_type: str) -> None:
    if length > covers_mod.COVER_UPLOAD_MAX_BYTES:
        raise ValueError("Cover upload too large (max 2 MB image)")
    item_id = path[len("/api/library/") : -len("/cover")]
    if not item_id or "/" in item_id:
        raise ValueError("Invalid library id")
    library.item_path(item_id)
    body_path = handler.spool_body(length)
    try:
        data = read_multipart_upload(body_path, content_type)
        item = library.set_cover(item_id, data)
    finally:
        body_path.unlink(missing_ok=True)
    handler.send_json(200, {"ok": True, "item": item, "library": library.status()})


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    shared = owner_from_body(body)
    oq = url_query_owner(shared)
    if path.startswith("/api/library/") and path.endswith("/sideload"):
        item_id = path[len("/api/library/") : -len("/sideload")].strip("/")
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        assert_own_catalog_only(shared, "send books to an e-reader from")
        row = library.get_item_row(item_id)
        if not library.is_registered(row):
            raise ValueError("Only catalogued bones can be sent to an e-reader")
        library.item_path(item_id)
        delivery = str(body.get("format") or "source").strip().lower()
        tok = sideload_tokens.create_token(handler._current_user, item_id, delivery)
        base = public_base_url(handler.config).rstrip("/")
        download_url = f"{base}/api/sideload/{tok['token']}"
        title = str(row.get("title") or row.get("filename") or "Book")
        handler.send_json(
            200,
            {
                "ok": True,
                "item_id": item_id,
                "title": title,
                "format": delivery,
                "download_url": download_url,
                "expires_at": tok["expires"],
                "expires_in_seconds": tok["expires_in_seconds"],
            },
        )
        return True
    if path.startswith("/api/library/") and path.endswith("/kindle-send"):
        item_id = path[len("/api/library/") : -len("/kindle-send")].strip("/")
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        assert_own_catalog_only(shared, "send books to an e-reader from")
        if not kindle_smtp.smtp_configured(handler.config):
            raise ValueError("Kindle email send is not configured on this server")
        to_addr = accounts.kindle_email_for(handler._current_user)
        if not to_addr:
            raise ValueError("Save your Send-to-Kindle address under Your tag first")
        row = library.get_item_row(item_id)
        if not library.is_registered(row):
            raise ValueError("Only catalogued bones can be sent to an e-reader")
        library.item_path(item_id)
        delivery = str(body.get("format") or "source").strip().lower()
        path_obj, mime, filename = device_delivery.resolve_delivery(item_id, delivery)
        title = str(row.get("title") or row.get("filename") or "Book")
        body_text = (
            f'"{title}" from BookPup ({handler._current_user}).\n'
            "If the book does not appear, confirm this From address is approved in "
            "Amazon → Send to Kindle → Approved e-mail addresses."
        )
        kindle_smtp.send_kindle_attachment(
            to_address=to_addr,
            subject=f"BookPup: {title}",
            body_text=body_text,
            file_path=path_obj,
            attachment_name=filename,
            content_type=mime,
        )
        handler.send_json(
            200,
            {
                "ok": True,
                "to": to_addr,
                "title": title,
                "format": delivery,
                "filename": filename,
            },
        )
        return True
    if path.startswith("/api/library/") and path.endswith("/view"):
        item_id = path[len("/api/library/") : -len("/view")]
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")

        def open_view() -> None:
            meta = prepare_view(item_id)
            title = item_id
            for row in library.list_items():
                if row.get("id") == item_id:
                    title = row.get("title") or title
                    break
            handler.send_json(
                200,
                {
                    "ok": True,
                    "id": item_id,
                    "format": meta["format"],
                    "converted": meta.get("converted", False),
                    "source_format": meta.get("source_format"),
                    "title": title,
                    "owner": shared,
                    "read_url": f"/api/library/{item_id}/read{oq}",
                    "comic_meta_url": (
                        f"/api/library/{item_id}/comic/meta{oq}"
                        if meta["format"] in ("cbz", "cbr", "cb7")
                        else None
                    ),
                },
            )

        with catalog_context(handler._current_user, shared):
            open_view()
        return True
    if path.startswith("/api/library/") and path.endswith("/reading"):
        item_id = path[len("/api/library/") : -len("/reading")]
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        loc = body.get("location")
        if loc is not None and not isinstance(loc, dict):
            raise ValueError("location must be an object")
        if shared:
            from .. import library_shares
            from .. import user_paths

            if not library_shares.can_read(handler._current_user, shared):
                raise PermissionError("Shared kennel access denied")
            user_paths.set_user(shared)
            try:
                library.item_path(item_id)
            finally:
                user_paths.set_user(handler._current_user)
            handler.send_json(
                200, reading.set_location(item_id, loc, shared_owner=shared)
            )
        else:
            library.item_path(item_id)
            handler.send_json(200, reading.set_location(item_id, loc))
        return True
    if path.startswith("/api/library/") and path.endswith("/bookmarks"):
        item_id = path[len("/api/library/") : -len("/bookmarks")]
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        label = str(body.get("label") or "").strip()
        loc = body.get("location")
        if not isinstance(loc, dict):
            raise ValueError("location required")
        if shared:
            from .. import library_shares
            from .. import user_paths

            if not library_shares.can_read(handler._current_user, shared):
                raise PermissionError("Shared kennel access denied")
            user_paths.set_user(shared)
            try:
                library.item_path(item_id)
            finally:
                user_paths.set_user(handler._current_user)
            mark = reading.add_bookmark(item_id, label, loc, shared_owner=shared)
            handler.send_json(
                201,
                {
                    "bookmark": mark,
                    "reading": reading.get_state(item_id, shared_owner=shared),
                },
            )
        else:
            library.item_path(item_id)
            mark = reading.add_bookmark(item_id, label, loc)
            handler.send_json(
                201, {"bookmark": mark, "reading": reading.get_state(item_id)}
            )
        return True
    assert_own_catalog_only(shared)
    if path.startswith("/api/library/") and path.endswith("/cover/images/search"):
        item_id = path[len("/api/library/") : -len("/cover/images/search")]
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        library.item_path(item_id)
        results = cover_search.search_cover_images(
            handler.config,
            title=str(body.get("title") or "").strip() or None,
            authors=str(body.get("authors") or "").strip() or None,
            isbn=str(body.get("isbn") or "").strip() or None,
            query=str(body.get("query") or "").strip() or None,
        )
        handler.send_json(200, {"ok": True, "results": results})
        return True
    if path.startswith("/api/library/") and path.endswith("/cover/url"):
        item_id = path[len("/api/library/") : -len("/cover/url")]
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        url = str(body.get("url") or "").strip()
        if not url:
            raise ValueError("url required")
        item = library.set_cover_from_url(item_id, url)
        handler.send_json(200, {"ok": True, "item": item, "library": library.status()})
        return True
    if path.startswith("/api/library/") and path.endswith("/metadata"):
        item_id = path[len("/api/library/") : -len("/metadata")]
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        item = library.update_metadata(
            item_id,
            body,
            use_cover=bool(body.get("use_cover")),
        )
        handler.send_json(200, {"ok": True, "item": item, "library": library.status()})
        return True
    if path.startswith("/api/library/") and path.endswith("/metadata/search"):
        item_id = path[len("/api/library/") : -len("/metadata/search")]
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        match = None
        for row in library.list_items():
            if row.get("id") == item_id:
                match = row
                break
        if not match:
            raise KeyError(item_id)
        if not library.is_staged(match) and not library.is_registered(match):
            raise ValueError("Metadata search not available for this item")
        library.item_path(item_id)
        results = metadata_search.search_metadata(
            title=str(body.get("title") or "").strip() or None,
            authors=str(body.get("authors") or "").strip() or None,
            isbn=str(body.get("isbn") or "").strip() or None,
        )
        handler.send_json(200, {"ok": True, "results": results})
        return True
    if path.startswith("/api/library/") and path.endswith("/register"):
        item_id = path[len("/api/library/") : -len("/register")]
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        item = library.register_item(
            item_id,
            body,
            use_cover=bool(body.get("use_cover")),
        )
        handler.send_json(200, {"ok": True, "item": item, "library": library.status()})
        return True
    if path.startswith("/api/library/") and path.endswith("/send"):
        item_id = path[len("/api/library/") : -len("/send")].strip("/")
        if not item_id or "/" in item_id:
            raise ValueError("Invalid library id")
        to_user = str(body.get("to") or "").strip()
        item = transfer.send_library_item(handler._current_user, to_user, item_id)
        handler.send_json(
            200,
            {
                "ok": True,
                "to": to_user,
                "item": item,
            },
        )
        return True
    if path.startswith("/api/library/save/"):
        staging_id = path[len("/api/library/save/") :].strip("/")
        transfer.assert_staging_access(
            staging_id, handler._current_user, handler._is_admin
        )
        title = str(body.get("title") or "").strip() or None
        item = library.save_from_staging(staging_id, title)
        handler.send_json(201, {"item": item, "library": library.status()})
        return True
    return False


def handle_delete(handler: RequestHandler, path: str, qs: dict | None = None) -> bool:
    if not path.startswith("/api/library/"):
        return False
    qs = qs or {}
    shared = owner_from_qs(qs)
    segments = [p for p in path.split("/") if p]
    if len(segments) == 5 and segments[0] == "api" and segments[1] == "library" and segments[3] == "bookmarks":
        item_id = segments[2]
        bookmark_id = segments[4]

        def drop_mark() -> None:
            if shared:
                from .. import library_shares
                from .. import user_paths

                if not library_shares.can_read(handler._current_user, shared):
                    raise PermissionError("Shared kennel access denied")
                user_paths.set_user(shared)
                try:
                    library.item_path(item_id)
                finally:
                    user_paths.set_user(handler._current_user)
                reading.delete_bookmark(item_id, bookmark_id, shared_owner=shared)
                handler.send_json(
                    200,
                    {
                        "ok": True,
                        "reading": reading.get_state(item_id, shared_owner=shared),
                    },
                )
            else:
                library.item_path(item_id)
                reading.delete_bookmark(item_id, bookmark_id)
                handler.send_json(200, {"ok": True, "reading": reading.get_state(item_id)})

        handler.dispatch(drop_mark)
        return True
    if len(segments) != 3 or segments[0] != "api" or segments[1] != "library":
        handler.send_json(404, {"error": "Not found"})
        return True
    item_id = segments[2]

    def action() -> None:
        library.delete_item(item_id)
        handler.send_json(200, {"ok": True, "library": library.status()})

    handler.dispatch(action)
    return True