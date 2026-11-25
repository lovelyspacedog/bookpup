"""Config and shared constants."""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path

VERSION = "1.7.10"
CONFIG_DIR = Path.home() / ".config" / "bookpup"
CONFIG_FILE = CONFIG_DIR / "config.json"
JOBS_DIR = CONFIG_DIR / "jobs"
STAGING_DIR = CONFIG_DIR / "staging"
LIBRARY_DIR = CONFIG_DIR / "library"
COVERS_DIR = CONFIG_DIR / "covers"
LIBRARY_INDEX = CONFIG_DIR / "library.json"
READING_STATE = CONFIG_DIR / "reading.json"
PIDFILE = CONFIG_DIR / "bookpup.pid"
LOG_FILE = CONFIG_DIR / "bookpup.log"
SESSIONS_FILE = CONFIG_DIR / "sessions.json"

DEFAULT_PORT = 18478
DEFAULT_USER = "book"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_IRC_SERVER = "irc.irchighway.net"
DEFAULT_IRC_PORT = 6667
DEFAULT_CHANNELS = ("#ebooks", "#bookz")
LIBRARY_QUOTA_BYTES = 10 * 1024 * 1024 * 1024
STAGING_TTL_SECONDS = 24 * 3600
IRC_POST_JOIN_COOLDOWN = 5
IRC_IDLE_DISCONNECT_SECONDS = 240
SEARCH_TIMEOUT = 120
DOWNLOAD_TIMEOUT = 600
MAX_DCC_RECEIVE_BYTES = 512 * 1024 * 1024
MAX_DCC_SEARCH_BYTES = 32 * 1024 * 1024
DOWNLOAD_OFFER_TIMEOUT = 120
BOT_STATUS_STALE_SECONDS = 2700
BOOK_OFFER_EXTEND_SECONDS = 60
BOOK_OFFER_MAX_SECONDS = 600
CSRF_HEADER = "X-Bookpup"

IRC_MOCK = os.environ.get("BOOKPUP_IRC_MOCK", "").strip() in ("1", "true", "yes")

XDCC_MOCK_ENV = os.environ.get("BOOKPUP_XDCC_MOCK", "").strip() in ("1", "true", "yes")

DEFAULT_SLSKD_URL = "http://127.0.0.1:5030"
DEFAULT_SOULSEEK_LIMITS = {
    "searches_per_hour": 20,
    "downloads_per_day": 10,
    "concurrent_downloads": 3,
}

SLSKD_MOCK = os.environ.get("BOOKPUP_SLSKD_MOCK", "").strip() in ("1", "true", "yes")

_config: dict | None = None
_config_mtime: float | None = None


def load_config() -> dict:
    global _config, _config_mtime
    mtime = CONFIG_FILE.stat().st_mtime if CONFIG_FILE.is_file() else None
    if _config is not None and _config_mtime == mtime:
        return _config
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
    else:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        password = secrets.token_urlsafe(12)
        config = {
            "username": DEFAULT_USER,
            "password": password,
            "port": DEFAULT_PORT,
            "host": DEFAULT_HOST,
            "irc_server": DEFAULT_IRC_SERVER,
            "irc_port": DEFAULT_IRC_PORT,
            "irc_tls": False,
            "library_quota_bytes": LIBRARY_QUOTA_BYTES,
        }
        CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")
        os.chmod(CONFIG_FILE, 0o600)
        print(f"Created {CONFIG_FILE} with password: {password}", file=sys.stderr)
        print(
            "Set public_url in config or BOOKPUP_PUBLIC_URL for KOReader sync and sideload links.",
            file=sys.stderr,
        )
    config.setdefault("port", DEFAULT_PORT)
    config.setdefault("host", DEFAULT_HOST)
    config.setdefault("username", DEFAULT_USER)
    config.setdefault("irc_server", DEFAULT_IRC_SERVER)
    config.setdefault("irc_port", DEFAULT_IRC_PORT)
    config.setdefault("irc_tls", False)
    config.setdefault("library_quota_bytes", LIBRARY_QUOTA_BYTES)
    config.setdefault("ai_enabled", False)
    config.setdefault("ai_listen_port", 18479)
    config.setdefault("ai_n_ctx", 4096)
    config.setdefault("ai_max_input_chars", 4500)
    config.setdefault("ai_max_output_tokens", 512)
    config.setdefault("ai_prompt_version", 1)
    config.setdefault("xdcc_search_enabled", True)
    config.setdefault("xdcc_search_url", "")
    config.setdefault("download_offer_timeout", DOWNLOAD_OFFER_TIMEOUT)
    config.setdefault("bot_status_stale_seconds", BOT_STATUS_STALE_SECONDS)
    config.setdefault("slskd_enabled", True)
    config.setdefault("slskd_url", DEFAULT_SLSKD_URL)
    config.setdefault("slskd_api_key", "")
    config.setdefault("slskd_username", "")
    config.setdefault("slskd_password", "")
    config.setdefault("slskd_download_root", "")
    config.setdefault("soulseek_search_timeout_sec", 20)
    config.setdefault("soulseek_response_limit", 300)
    config.setdefault("soulseek_limits", dict(DEFAULT_SOULSEEK_LIMITS))
    _config = config
    _config_mtime = mtime
    return config


def download_offer_timeout() -> float:
    return float(load_config().get("download_offer_timeout", DOWNLOAD_OFFER_TIMEOUT))


def bot_status_stale_seconds() -> float:
    return float(load_config().get("bot_status_stale_seconds", BOT_STATUS_STALE_SECONDS))


def public_url_configured(config: dict | None = None) -> bool:
    env = os.environ.get("BOOKPUP_PUBLIC_URL", "").strip()
    if env:
        return True
    cfg = config if config is not None else load_config()
    return bool(str(cfg.get("public_url") or "").strip())


def public_base_url(config: dict | None = None) -> str:
    """HTTPS base URL for KOReader sync and outbound identity (no trailing slash)."""
    env = os.environ.get("BOOKPUP_PUBLIC_URL", "").strip()
    if env:
        url = env.rstrip("/")
    else:
        cfg = config if config is not None else load_config()
        url = str(cfg.get("public_url") or "").strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def user_agent() -> str:
    base = public_base_url()
    if base:
        return f"BookPup/{VERSION} (household library; +{base})"
    return f"BookPup/{VERSION} (household library)"


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    if not LIBRARY_INDEX.exists():
        LIBRARY_INDEX.write_text(json.dumps({"items": []}, indent=2) + "\n")