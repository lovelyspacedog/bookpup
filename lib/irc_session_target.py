"""IRC connection target for a job (catalogue or XDCC fetch)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import irc_targets
from . import xdcc_search


@dataclass(frozen=True)
class SessionTarget:
    id: str
    network: str
    channel: str
    server: str
    port: int
    use_tls: bool

    @property
    def display(self) -> str:
        if self.channel:
            return f"{self.network} · {self.channel}"
        return self.network

    def session_key(self) -> tuple[str, int, bool]:
        return (self.server, self.port, self.use_tls)

    def binding(self) -> tuple[str, int, bool, str]:
        return (self.server, self.port, self.use_tls, self.channel)


def _from_irc(t: irc_targets.IrcTarget) -> SessionTarget:
    return SessionTarget(
        id=t.id,
        network=t.network,
        channel=t.channel,
        server=t.server,
        port=t.port,
        use_tls=t.use_tls,
    )


def target_for_job(job: dict[str, Any]) -> SessionTarget:
    xdcc = job.get("xdcc")
    if isinstance(xdcc, dict):
        xdcc = xdcc_search.ensure_xdcc_server(xdcc)
        server = str(xdcc.get("server") or "").strip()
        channel = str(xdcc.get("channel") or "").strip()
        if server and channel:
            network = str(xdcc.get("network") or "XDCC").strip() or "XDCC"
            try:
                port = int(xdcc.get("port") or 6667)
            except (TypeError, ValueError):
                port = 6667
            use_tls = bool(xdcc.get("use_tls"))
            tid = str(job.get("channel") or irc_targets.XDCC_INDEX_ID)
            return SessionTarget(
                id=tid,
                network=network,
                channel=channel,
                server=server,
                port=port,
                use_tls=use_tls,
            )
    raw = str(job.get("channel") or irc_targets.DEFAULT_SEARCH_TARGET)
    return _from_irc(irc_targets.resolve_target(raw))