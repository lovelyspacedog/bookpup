"""Client IP for rate limits — trust forwarded headers only from loopback peers."""

from __future__ import annotations

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


def client_key(peer_host: str | None, headers: dict[str, str] | None) -> str:
    peer = str(peer_host or "").strip().lower()
    hdrs = headers or {}
    if peer in _LOOPBACK:
        xff = hdrs.get("X-Forwarded-For") or hdrs.get("x-forwarded-for") or ""
        if xff.strip():
            client = xff.split(",")[0].strip()
            if client:
                return client
        fwd = hdrs.get("Forwarded") or hdrs.get("forwarded") or ""
        if fwd.strip():
            # e.g. for=1.2.3.4;proto=https;by=...
            for segment in fwd.split(","):
                segment = segment.strip()
                for piece in segment.split(";"):
                    piece = piece.strip()
                    if piece.lower().startswith("for="):
                        val = piece[4:].strip().strip('"')
                        if val.startswith("[") and "]" in val:
                            val = val[1 : val.index("]")]
                        elif ":" in val and val.count(":") == 1 and not val.startswith("["):
                            val = val.split(":", 1)[0]
                        if val:
                            return val
    return peer or "unknown"