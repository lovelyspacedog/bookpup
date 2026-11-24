"""HTTP fallback when Undernet !get / Gutenberg on-demand bots refuse DCC."""

from __future__ import annotations

import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .irc_client import DccOffer, DownloadRequestError
from .metadata_search import user_agent

GUTENBERG_URL_RE = re.compile(
    r"https?://(?:www\.)?gutenberg\.org/ebooks/(\d+)",
    re.IGNORECASE,
)
PG_TAG_RE = re.compile(r"\[PG-(\d+)\]", re.IGNORECASE)
GET_CMD_RE = re.compile(r"^!get\s+(\d+)\s*$", re.IGNORECASE)

_GUTENBERG_HOSTS = frozenset({"www.gutenberg.org", "gutenberg.org"})

MAX_BYTES = 96 * 1024 * 1024
_READ_CHUNK = 256 * 1024

_EBOOK_SUFFIXES = (
    (".epub.noimages", ".epub"),
    (".epub.images", ".epub"),
    (".epub3.noimages", ".epub"),
    (".epub3.images", ".epub"),
    (".kindle.noimages", ".mobi"),
    (".kindle.images", ".mobi"),
    (".pdf.noimages", ".pdf"),
    (".pdf.images", ".pdf"),
    (".txt.utf-8", ".txt"),
)


def resolve_gutenberg_id(*hints: str | None) -> int | None:
    for raw in hints:
        text = str(raw or "")
        if not text:
            continue
        m = GUTENBERG_URL_RE.search(text)
        if m:
            return int(m.group(1))
        m = PG_TAG_RE.search(text)
        if m:
            return int(m.group(1))
        m = GET_CMD_RE.match(text.strip())
        if m:
            return int(m.group(1))
    return None


def _attempt_gutenberg_fallback(
    command: str,
    reason: str,
    title: str | None,
) -> bool:
    gid = resolve_gutenberg_id(reason, title, command)
    if gid is None:
        return False
    if GET_CMD_RE.match((command or "").strip()):
        return True
    if GUTENBERG_URL_RE.search(reason or ""):
        return True
    if PG_TAG_RE.search((title or "") + reason):
        return True
    return False


def _assert_gutenberg_url(url: str) -> str:
    from .url_safety import assert_fetchable_https_url

    safe = assert_fetchable_https_url(url)
    host = (urllib.parse.urlparse(safe).hostname or "").lower()
    if host not in _GUTENBERG_HOSTS:
        raise ValueError("URL is not Project Gutenberg")
    return safe


def _looks_like_html_error(data: bytes) -> bool:
    head = data[:4096].lstrip().lower()
    if not head:
        return True
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        return b"<title>" in head and (
            b"maintenance" in head or b"error" in head or b"not found" in head
        )
    return False


def _files_prefix(gid: int) -> str:
    if gid >= 1000:
        return str(gid // 100)
    return str(gid // 10)


def _candidate_urls(gid: int) -> list[tuple[str, str]]:
    base = f"https://www.gutenberg.org/ebooks/{gid}"
    prefix = _files_prefix(gid)
    files_base = f"https://www.gutenberg.org/files/{prefix}/{gid}"
    out: list[tuple[str, str]] = []
    for suffix, ext in _EBOOK_SUFFIXES:
        out.append((base + suffix, ext))
    out.append((f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.epub", ".epub"))
    out.append((f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt", ".txt"))
    out.append((f"{files_base}/{gid}-0.txt", ".txt"))
    out.append((f"{files_base}/{gid}.txt", ".txt"))
    out.append((f"{files_base}/{gid}-h.zip", ".zip"))
    return out


def _download_url(url: str, dest: Path) -> int:
    url = _assert_gutenberg_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    total = 0
    with urllib.request.urlopen(req, timeout=90) as resp:
        status = getattr(resp, "status", 200) or 200
        if status >= 400:
            raise urllib.error.HTTPError(url, status, "", resp.headers, None)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fh:
            while True:
                chunk = resp.read(_READ_CHUNK)
                if not chunk:
                    break
                if total == 0 and _looks_like_html_error(chunk):
                    raise ValueError("Gutenberg returned an HTML page, not a book file")
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("Project Gutenberg file too large")
                fh.write(chunk)
    if total < 128:
        dest.unlink(missing_ok=True)
        raise ValueError("Downloaded file empty")
    return total


def _is_pg_unavailable(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError) and exc.code in (502, 503, 504):
        return True
    msg = str(exc).lower()
    return "html page" in msg or "maintenance" in msg


def _try_candidates(gid: int, dest: Path) -> tuple[str, str, int]:
    last_err: Exception | None = None
    unavailable = 0
    tries = 0
    for url, ext in _candidate_urls(gid):
        tmp = dest.with_suffix(dest.suffix + ".part")
        tries += 1
        try:
            size = _download_url(url, tmp)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(tmp, dest)
            return url, ext, size
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, OSError) as exc:
            last_err = exc
            if _is_pg_unavailable(exc):
                unavailable += 1
            tmp.unlink(missing_ok=True)
            continue
    if unavailable and unavailable == tries:
        raise ValueError(
            f"Project Gutenberg is temporarily unavailable (site maintenance or 503) "
            f"for ebook #{gid} — try again in a few hours."
        )
    raise ValueError(
        f"No Project Gutenberg download for #{gid}"
        + (f" ({last_err})" if last_err else "")
    )


@dataclass(frozen=True)
class GutenbergFetchResult:
    offer: DccOffer
    feed: str


def gutenberg_fallback_after_irc_refusal(
    *,
    reason: str,
    command: str,
    title: str | None,
    dest_path: Path,
    on_status: Callable[[str], None],
) -> GutenbergFetchResult | None:
    """If IRC refused a !get / PG hit, download EPUB (else best format) from gutenberg.org."""
    if not _attempt_gutenberg_fallback(command, reason, title):
        return None
    gid = resolve_gutenberg_id(reason, title, command)
    if gid is None:
        return None
    on_status(f"IRC refused — trying Project Gutenberg #{gid}…")
    try:
        url, ext, size = _try_candidates(gid, dest_path)
    except ValueError as exc:
        raise DownloadRequestError(str(exc)) from exc
    name = f"pg{gid}{ext}"
    return GutenbergFetchResult(
        offer=DccOffer(filename=name, host="", port=0, size=size),
        feed=f"Project Gutenberg fallback: {url}",
    )