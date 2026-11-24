"""Reader AI summarize / ask."""

from __future__ import annotations

from pathlib import Path

from .. import library, reader_ai
from ..convert import prepare_view
from ._types import RequestHandler


def reader_ai_paths(path: str, suffix: str) -> tuple[str, Path, str]:
    item_id = path[len("/api/library/") : -len(suffix)]
    if not item_id or "/" in item_id:
        raise ValueError("Invalid library id")
    library.item_path(item_id)
    meta = prepare_view(item_id)
    file_path = Path(meta["path"])
    fmt = str(meta.get("format") or "").lower()
    return item_id, file_path, fmt


def route_summarize(handler: RequestHandler, path: str, body: dict) -> None:
    try:
        item_id, file_path, view_fmt = reader_ai_paths(path, "/ai/summarize")
        if "format" not in body:
            body = {**body, "format": view_fmt}
        excerpt_key, excerpt, _n = reader_ai.excerpt_from_request(file_path, body)
        client = f"{handler.client_address[0]}:{handler.headers.get('Authorization', '')[:12]}"
        out = reader_ai.summarize(item_id, excerpt_key, excerpt, client_key=client)
        handler.send_json(200, out)
    except PermissionError as exc:
        handler.send_json(403, {"error": str(exc)})
    except FileNotFoundError as exc:
        handler.send_json(403, {"error": str(exc)})
    except ValueError as exc:
        msg = str(exc)
        code = 413 if "Not enough text" in msg else 400
        handler.send_json(code, {"error": msg})


def route_ask(handler: RequestHandler, path: str, body: dict) -> None:
    try:
        item_id, file_path, view_fmt = reader_ai_paths(path, "/ai/ask")
        if "format" not in body:
            body = {**body, "format": view_fmt}
        excerpt_key, excerpt, _n = reader_ai.excerpt_from_request(file_path, body)
        history = body.get("history")
        if history is not None and not isinstance(history, list):
            raise ValueError("history must be a list")
        client = f"{handler.client_address[0]}:{handler.headers.get('Authorization', '')[:12]}"
        out = reader_ai.ask(
            item_id,
            excerpt_key,
            excerpt,
            str(body.get("question") or ""),
            history if isinstance(history, list) else None,
            client_key=client,
        )
        handler.send_json(200, out)
    except PermissionError as exc:
        handler.send_json(403, {"error": str(exc)})
    except FileNotFoundError as exc:
        handler.send_json(403, {"error": str(exc)})
    except ValueError as exc:
        msg = str(exc)
        code = 413 if "Not enough text" in msg else 400
        handler.send_json(code, {"error": msg})


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path.startswith("/api/library/") and path.endswith("/ai/summarize"):
        handler.dispatch(lambda: route_summarize(handler, path, body))
        return True
    if path.startswith("/api/library/") and path.endswith("/ai/ask"):
        handler.dispatch(lambda: route_ask(handler, path, body))
        return True
    return False