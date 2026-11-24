"""HTTP handler and entry point."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import accounts, auth, jobs, kosync
from . import irc_targets
from .core import CSRF_HEADER, VERSION, ensure_dirs, load_config
from .irc_worker import worker
from .scheduled_sniff import start_scheduler
from .staging import cleanup_staging
from .routes import (
    admin,
    auth_routes,
    irc as irc_routes,
    jobs as jobs_routes,
    kosync as kosync_routes,
    library as library_routes,
    library_shares as library_shares_routes,
    opds as opds_routes,
    public as public_routes,
    reader_ai_routes,
    pack_chat as pack_chat_routes,
    search as search_routes,
    session_routes,
    staging as staging_routes,
    static_files,
    walk_trail as walk_trail_routes,
)

# Re-export for compatibility
index_html = static_files.index_html
resolve_static = static_files.resolve_static
kosync_path = kosync_routes.kosync_path
opds_path = opds_routes.opds_path


class Handler(BaseHTTPRequestHandler):
    config: dict = {}
    _current_user: str = ""
    _is_admin: bool = False

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("bookpup - %s\n" % (fmt % args))

    def log_request(self, code="-", size="-") -> None:
        if self.command == "GET" and isinstance(code, int) and code < 400:
            if self.path.startswith("/static/"):
                return
        super().log_request(code, size)

    def send_json(self, code: int, data: dict | list) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_ko_json(self, code: int, data: dict | list) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", kosync.KO_JSON)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _header_map(self) -> dict[str, str]:
        return {str(k): str(v) for k, v in self.headers.items()}

    def send_bytes(self, body: bytes, content_type: str, download_name: str | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(body)

    def _validated_irc_channel(self, raw: object) -> str:
        cid = irc_targets.normalize_channel_id(str(raw or "irchighway:ebooks"))
        if cid in (
            irc_targets.SEARCH_ALL_ID,
            irc_targets.XDCC_INDEX_ID,
            irc_targets.SOULSEEK_INDEX_ID,
        ):
            return cid
        if irc_targets.is_xdcc_row_target(cid):
            return cid
        try:
            return irc_targets.resolve_target(cid).id
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    def require_auth(self) -> bool:
        user = auth.session_user(self.headers.get("Authorization"))
        if not user:
            self.send_json(401, {"error": "Authentication required"})
            return False
        accounts.migrate_legacy()
        from . import user_paths

        user_paths.set_user(user)
        self._current_user = user
        self._is_admin = accounts.is_admin(user)
        return True

    def require_admin(self) -> bool:
        if not self.require_auth():
            return False
        if not self._is_admin:
            self.send_json(403, {"error": "Admin access required"})
            return False
        return True

    def require_csrf(self) -> bool:
        if self.headers.get(CSRF_HEADER) == "1":
            return True
        self.send_json(403, {"error": f"Missing {CSRF_HEADER} header; reload the page"})
        return False

    def read_json(self, length: int) -> dict:
        if length > 256 * 1024:
            raise ValueError("Request too large")
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Expected object")
        return data

    def dispatch(self, action) -> None:
        try:
            action()
        except KeyError as exc:
            self.send_json(404, {"error": str(exc) or "Not found"})
        except PermissionError as exc:
            self.send_json(403, {"error": str(exc) or "Forbidden"})
        except ValueError as exc:
            msg = str(exc)
            if "quota" in msg.lower():
                self.send_json(507, {"error": msg})
            else:
                self.send_json(400, {"error": msg})
        except (TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": str(exc) or "Request failed"})

    def spool_body(self, length: int) -> Path:
        if length <= 0:
            raise ValueError("Empty request body")
        max_bytes = 2 * 1024 * 1024 * 1024
        if length > max_bytes:
            raise ValueError("Upload too large (2GB max)")
        fd, name = tempfile.mkstemp(prefix="bookpup-body-")
        path = Path(name)
        try:
            with open(fd, "wb") as out:
                shutil.copyfileobj(self.rfile, out, length)
        except OSError:
            path.unlink(missing_ok=True)
            raise
        return path

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html", "/manifest.webmanifest", "/sw.js") or path.startswith(
            "/static/"
        ):
            self.dispatch(lambda: static_files.route_get_public(self, path))
            return
        if path == "/api/config":
            self.dispatch(lambda: public_routes.route_public_config(self))
            return
        if path == "/api/capabilities":
            self.dispatch(lambda: public_routes.route_public_capabilities(self))
            return
        if path == "/api/health":
            self.dispatch(lambda: public_routes.route_public_health(self))
            return
        if opds_path(path):
            self.dispatch(lambda: opds_routes.route_opds_get(self, path))
            return
        if kosync_path(path):
            self.dispatch(lambda: kosync_routes.route_kosync_get(self, path))
            return
        if path.startswith("/api/staging/") and path.endswith("/raw"):
            if not self.require_auth():
                return
            sid = path[len("/api/staging/") : -len("/raw")]
            self.dispatch(lambda: staging_routes.send_staging_raw(self, sid))
            return
        if not self.require_auth():
            return
        qs = parse_qs(parsed.query)
        self.dispatch(lambda: self._route_get(path, qs))

    def _route_get(self, path: str, qs: dict) -> None:
        for mod in (
            session_routes,
            auth_routes,
            admin,
            library_shares_routes,
            library_routes,
            jobs_routes,
            irc_routes,
            pack_chat_routes,
            search_routes,
        ):
            if mod.handle_get(self, path, qs):
                return
        self.send_json(404, {"error": "Not found"})

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if path != "/syncs/progress":
            self.send_json(405, {"error": "Method not allowed"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        self.dispatch(lambda: kosync_routes.route_kosync_put(self, length))

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        if path == "/users/create":
            self.dispatch(lambda: kosync_routes.route_kosync_create(self, length))
            return
        if path == "/api/login":
            self.dispatch(lambda: auth_routes.route_login(self, length))
            return
        if not self.require_auth() or not self.require_csrf():
            return
        if library_routes.try_post_early(self, path, length):
            return
        self.dispatch(lambda: self._route_post(path, length))

    def _route_post(self, path: str, length: int) -> None:
        body = self.read_json(length)
        for mod in (
            irc_routes,
            pack_chat_routes,
            search_routes,
            jobs_routes,
            auth_routes,
            library_shares_routes,
            library_routes,
            staging_routes,
            admin,
            reader_ai_routes,
            walk_trail_routes,
        ):
            if mod.handle_post(self, path, body):
                return
        self.send_json(404, {"error": "Not found"})

    def do_DELETE(self) -> None:
        if not self.require_auth() or not self.require_csrf():
            return
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        for mod in (
            admin,
            search_routes,
            library_shares_routes,
            library_routes,
            pack_chat_routes,
        ):
            if mod.handle_delete(self, path, qs):
                return
        self.send_json(404, {"error": "Not found"})


def main() -> None:
    ensure_dirs()
    accounts.migrate_legacy()
    restored = auth.bootstrap_sessions()
    if restored:
        print(f"bookpup: restored {restored} session(s)", file=sys.stderr)
    cleanup_staging()
    try:
        from .import_session import cleanup_stale_sessions

        cleanup_stale_sessions()
    except OSError:
        pass
    recovered = jobs.recover_interrupted_jobs()
    if recovered:
        print(f"bookpup: recovered {recovered} interrupted job(s)", file=sys.stderr)
    config = load_config()
    Handler.config = config
    worker.start()
    start_scheduler()
    host = str(config.get("host", "127.0.0.1"))
    port = int(config["port"])
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"BookPup v{VERSION} listening on {host}:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()