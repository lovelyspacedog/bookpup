"""Outbound URL policy for server-side fetches (SSRF mitigation)."""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.request


def _host_is_public(host: str) -> bool:
    host = (host or "").strip().lower().rstrip(".")
    if not host or host == "localhost":
        return False
    if host.endswith(".localhost") or host.endswith(".local"):
        return False
    try:
        packed = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for item in packed:
        addr = item[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def assert_fetchable_https_url(url: str) -> str:
    raw = str(url or "").strip()
    if raw.startswith("http://"):
        raw = "https://" + raw[7:]
    elif not raw.startswith("https://"):
        raise ValueError("Invalid cover URL (https required)")
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Invalid cover URL")
    if parsed.username or parsed.password:
        raise ValueError("Invalid cover URL")
    if not _host_is_public(parsed.hostname):
        raise ValueError("Cover URL host not allowed")
    return raw


def assert_ntfy_server_url(server: str) -> str:
    raw = str(server or "").strip() or "https://ntfy.sh"
    if not raw.startswith("https://"):
        raise ValueError("ntfy_server must use https")
    parsed = urllib.parse.urlparse(raw)
    if not parsed.hostname:
        raise ValueError("Invalid ntfy_server")
    if not _host_is_public(parsed.hostname):
        raise ValueError("ntfy_server host not allowed")
    return raw.rstrip("/")