"""Static assets and index.html."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from ..core import VERSION
from ._types import RequestHandler

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
STATIC_MIME = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".woff2": "font/woff2",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".png": "image/png",
}


def _versioned_text(name: str) -> bytes:
    return (STATIC_DIR / name).read_text().replace("__VERSION__", VERSION).encode()


def index_html() -> bytes:
    return _versioned_text("index.html")


def service_worker_js() -> bytes:
    return _versioned_text("sw.js")


def web_manifest() -> bytes:
    return (STATIC_DIR / "manifest.webmanifest").read_bytes()


def resolve_static(rel: str) -> Path | None:
    if not rel or ".." in rel.split("/"):
        return None
    base = STATIC_DIR.resolve()
    path = (STATIC_DIR / rel).resolve()
    if not str(path).startswith(str(base)):
        return None
    if path.is_file():
        return path
    return None


def route_get_public(handler: RequestHandler, path: str) -> None:
    if path in ("/", "/index.html"):
        handler.send_bytes(index_html(), "text/html; charset=utf-8")
    elif path == "/manifest.webmanifest":
        handler.send_bytes(web_manifest(), STATIC_MIME[".webmanifest"])
    elif path == "/sw.js":
        body = service_worker_js()
        handler.send_response(200)
        handler.send_header("Content-Type", "text/javascript; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Service-Worker-Allowed", "/")
        handler.end_headers()
        handler.wfile.write(body)
    elif path.startswith("/static/"):
        rel = path[len("/static/") :]
        file_path = resolve_static(rel)
        if not file_path:
            handler.send_json(404, {"error": "Not found"})
            return
        ext = file_path.suffix.lower()
        ctype = STATIC_MIME.get(ext) or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        body = file_path.read_bytes()
        if ext in (".js", ".css"):
            handler.send_response(200)
            handler.send_header("Content-Type", ctype)
            handler.send_header("Content-Length", str(len(body)))
            handler.send_header("Cache-Control", "no-cache")
            handler.end_headers()
            handler.wfile.write(body)
        else:
            handler.send_bytes(body, ctype)
    else:
        handler.send_json(404, {"error": "Not found"})