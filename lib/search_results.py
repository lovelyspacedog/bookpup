"""Parse SearchBot txt.zip listings."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

INFO_RE = re.compile(r"\s*::\s*INFO\s*::\s*", re.I)
INFO_BLOCK_RE = re.compile(r"\s*::\s*INFO\s*::(?:\s*\S+)?", re.I)
HASH_META_RE = re.compile(r"\s*::\s*HASH\s*::\s*[0-9a-f]+\s*", re.I)
SIZE_SUFFIX_RE = re.compile(
    r"\s+-\s+\d+(?:\.\d+)?\s*(?:[KMGT]?B|bytes?)\s*$",
    re.I,
)
FUSED_SIZE_SUFFIX_RE = re.compile(r"\d+(?:\.\d+)?[KMGT]B\s*$", re.I)
EXT_TAIL_RE = re.compile(r"\.[a-z0-9]{2,5}$", re.I)
# Undernet SearchBot: "1059831 | Author - Title | Project Gutenberg"
CATALOG_META_RE = re.compile(
    r"^(?P<id>\d+)\s*\|\s*(?P<title>.+?)\s*\|\s*(?P<source>.+?)\s*$"
)
_GET_ID_RE = re.compile(r"^(?P<id>\d+)$")
_ON_DEMAND_NOISE_RE = re.compile(r"ON-?DEMAND", re.I)


def _strip_fused_size(rest: str) -> tuple[str, str | None]:
    m = FUSED_SIZE_SUFFIX_RE.search(rest)
    if not m:
        return rest, None
    body = rest[: m.start()]
    if not EXT_TAIL_RE.search(body):
        return rest, None
    return body, m.group(0).strip()
SERVER_LINE_RE = re.compile(r"^!(?P<server>\S+)\s+(?P<rest>.+)$")


@dataclass(frozen=True)
class SearchResult:
    server: str
    title: str
    size_hint: str | None
    command: str
    display: str

    def to_dict(self) -> dict:
        return {
            "server": self.server,
            "title": self.title,
            "size_hint": self.size_hint,
            "command": self.command,
            "display": self.display,
        }


def normalize_download_body(body: str) -> str:
    """File name only — strips SearchBot metadata and fused size suffixes."""
    text, _ = _split_command_rest(body)
    return text


def clean_command_body(body: str) -> str:
    """Drop SearchBot ::INFO:: / ::HASH:: trailers so bots accept the file line."""
    text = (body or "").strip()
    text = INFO_BLOCK_RE.sub("", text)
    text = HASH_META_RE.sub("", text)
    text = _ON_DEMAND_NOISE_RE.sub("", text).strip()
    return re.sub(r"\s{2,}", " ", text).strip()


def _split_command_rest(rest: str) -> tuple[str, str | None]:
    text = rest.strip()
    size_hint = None
    info_m = re.search(r"::\s*INFO\s*::\s*(\S+)", text, re.I)
    if info_m:
        size_hint = info_m.group(1)
    text = clean_command_body(text)
    sm = SIZE_SUFFIX_RE.search(text)
    if sm:
        hint = sm.group(0).strip().lstrip("-").strip()
        return text[: sm.start()].rstrip(), size_hint or hint
    body, fused = _strip_fused_size(text)
    if fused:
        return body, size_hint or fused
    return text, size_hint


def parse_result_line(line: str) -> SearchResult | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    line = INFO_RE.sub("", line).strip()
    if not line.startswith("!"):
        return None
    m = SERVER_LINE_RE.match(line)
    if not m:
        return None
    server = m.group("server")
    rest = m.group("rest").strip()
    command_body, size_hint = _split_command_rest(rest)
    command = f"!{server} {command_body}"
    title = command_body
    return SearchResult(
        server=server,
        title=title,
        size_hint=size_hint,
        command=command,
        display=line,
    )


def _collect_catalog_titles(text: str) -> dict[str, str]:
    catalog: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = CATALOG_META_RE.match(line)
        if m:
            catalog[m.group("id")] = m.group("title").strip()
    return catalog


def _enrich_undernet_get_row(row: SearchResult, catalog: dict[str, str]) -> SearchResult:
    if row.server.lower() != "get" or not catalog:
        return row
    m = _GET_ID_RE.match(row.title.strip())
    if not m:
        return row
    label = catalog.get(m.group("id"))
    if not label:
        return row
    return SearchResult(
        server=row.server,
        title=label,
        size_hint=row.size_hint,
        command=row.command,
        display=row.display,
    )


def parse_results_text(text: str) -> list[SearchResult]:
    catalog = _collect_catalog_titles(text)
    out: list[SearchResult] = []
    for line in text.splitlines():
        row = parse_result_line(line)
        if row:
            out.append(_enrich_undernet_get_row(row, catalog))
    return out


def parse_results_zip(zip_path: str | Path) -> list[SearchResult]:
    path = Path(zip_path)
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not names:
            raise ValueError("no .txt in results zip")
        text = zf.read(names[0]).decode("utf-8", errors="replace")
    return parse_results_text(text)