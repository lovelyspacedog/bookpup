"""Parse KOReader metadata.*.lua sidecars (Calibre sync plugin compatible fields)."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from . import file_digest, library

METADATA_LUA_RE = re.compile(r"^metadata\.[^/\\]+\.lua$", re.IGNORECASE)
_HEX32_RE = re.compile(r"^[a-f0-9]{32}$", re.IGNORECASE)

_LUA_STR = re.compile(r'\["([^"]+)"\]\s*=\s*"((?:\\.|[^"\\])*)"')
_LUA_NUM = re.compile(r'\["([^"]+)"\]\s*=\s*([\d.]+)')
_LUA_BOOL = re.compile(r'\["([^"]+)"\]\s*=\s*(true|false)')


def _unescape_lua_string(raw: str) -> str:
    return raw.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def _hex32(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = str(raw).strip().lower()
    return cleaned if _HEX32_RE.fullmatch(cleaned) else None


def _norm_title(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (raw or "").lower()).strip()


def partial_id_from_archive_path(archive_path: str | None) -> str | None:
    """KOReader hash/docsettings paths embed the partial MD5 in folder names."""
    if not archive_path:
        return None
    norm = archive_path.replace("\\", "/")
    for segment in reversed(Path(norm).parts):
        low = segment.lower()
        if low.endswith(".sdr"):
            hid = _hex32(segment[: -len(".sdr")])
            if hid:
                return hid
        hid = _hex32(segment)
        if hid:
            return hid
    return None


def book_basename_from_archive_path(archive_path: str | None) -> str | None:
    if not archive_path:
        return None
    parent = Path(archive_path.replace("\\", "/")).parent.name
    if parent.lower().endswith(".sdr"):
        return parent[: -len(".sdr")]
    return None


def parse_metadata_lua(text: str) -> dict[str, Any]:
    """Best-effort parse of KOReader sidecar (no full Lua interpreter)."""
    body = text.strip()
    if body.lower().startswith("return"):
        body = body[6:].strip()
    if body.startswith("{"):
        body = body[1:]
    out: dict[str, Any] = {}
    for key, val in _LUA_NUM.findall(body):
        try:
            out[key] = float(val) if "." in val else int(val)
        except ValueError:
            out[key] = val
    for key, val in _LUA_BOOL.findall(body):
        out[key] = val == "true"
    for key, val in _LUA_STR.findall(body):
        out[key] = _unescape_lua_string(val)
    sm = re.search(
        r'\["summary"\]\s*=\s*\{([^}]*)\}',
        text,
        re.DOTALL,
    )
    if sm:
        summary: dict[str, Any] = {}
        block = sm.group(1)
        for key, val in _LUA_STR.findall(block):
            summary[key] = _unescape_lua_string(val)
        for key, val in _LUA_NUM.findall(block):
            summary[key] = val
        out["summary"] = summary
    st = re.search(r'\["stats"\]\s*=\s*\{([^}]*)\}', text, re.DOTALL)
    if st:
        stats: dict[str, Any] = {}
        block = st.group(1)
        for key, val in _LUA_STR.findall(block):
            stats[key] = _unescape_lua_string(val)
        for key, val in _LUA_NUM.findall(block):
            stats[key] = val
        out["stats"] = stats
    highlights: list[dict[str, str]] = []
    for block in re.finditer(r'\["text"\]\s*=\s*"((?:\\.|[^"\\])*)"', text):
        highlights.append({"text": _unescape_lua_string(block.group(1))})
    if highlights:
        out["annotation_texts"] = highlights
    return out


def highlights_markdown(parsed: dict[str, Any]) -> str:
    lines: list[str] = []
    for row in parsed.get("annotation_texts") or []:
        text = str(row.get("text") or "").strip()
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)


def progress_from_sidecar(parsed: dict[str, Any]) -> tuple[float | None, str | None, str | None]:
    pct = parsed.get("percent_finished")
    try:
        percentage = float(pct) if pct is not None else None
    except (TypeError, ValueError):
        percentage = None
    progress = parsed.get("last_xpointer") or parsed.get("page")
    if progress is not None:
        progress = str(progress)
    summary = parsed.get("summary") if isinstance(parsed.get("summary"), dict) else {}
    status = str(summary.get("status") or "").strip() or None
    return percentage, progress, status


def basename_candidates(
    parsed: dict[str, Any],
    upload_name: str,
    archive_path: str | None = None,
) -> list[str]:
    names: list[str] = []
    doc_path = str(parsed.get("doc_path") or "").strip()
    if doc_path:
        names.append(Path(doc_path).name)
    sdr_base = book_basename_from_archive_path(archive_path)
    if sdr_base:
        names.append(sdr_base)
    upl = Path(upload_name).name
    if upl.startswith("metadata."):
        rest = upl[len("metadata.") :]
        if rest.endswith(".lua"):
            names.append(rest[: -len(".lua")])
    return names


def partial_id_from_parsed(parsed: dict[str, Any]) -> str | None:
    for key in ("partial_md5_checksum", "partial_md5", "doc_hash", "hash"):
        hid = _hex32(str(parsed.get(key) or ""))
        if hid:
            return hid
    return None


def match_registered_item(
    parsed: dict[str, Any],
    upload_name: str,
    *,
    archive_path: str | None = None,
    partial_index: dict[str, str] | None = None,
) -> str | None:
    if partial_index is None:
        partial_index = library.ensure_all_registered_digests()

    for hid in (
        partial_id_from_archive_path(archive_path),
        partial_id_from_parsed(parsed),
    ):
        if hid and hid in partial_index:
            return partial_index[hid]

    stats = parsed.get("stats") if isinstance(parsed.get("stats"), dict) else {}
    title = str(stats.get("title") or "").strip()
    authors = str(stats.get("authors") or "").strip().lower()
    norm_title = _norm_title(title)

    for base in basename_candidates(parsed, upload_name, archive_path):
        base_low = base.lower()
        fn_md5 = file_digest.filename_md5(base)
        base_norm = _norm_title(Path(base).stem)
        for row in library.list_registered_items():
            item_id = str(row["id"])
            if str(row.get("filename_md5") or "").lower() == fn_md5:
                return item_id
            if norm_title and _norm_title(str(row.get("title") or "")) == base_norm:
                return item_id
            if str(row.get("filename") or "").lower() == base_low:
                return item_id
            stem = Path(str(row.get("filename") or "")).stem.lower()
            if stem and stem == Path(base).stem.lower():
                return item_id

    if norm_title:
        for row in library.list_registered_items():
            rt = _norm_title(str(row.get("title") or ""))
            if rt == norm_title:
                return str(row["id"])
            if rt and norm_title and (norm_title in rt or rt in norm_title):
                ra = str(row.get("authors") or "").strip().lower()
                if not authors or not ra or authors.split()[0] in ra or ra.split()[0] in authors:
                    return str(row["id"])
    return None


def apply_sidecar(item_id: str, parsed: dict[str, Any], *, upload_name: str = "") -> dict:
    percentage, progress, status = progress_from_sidecar(parsed)
    highlights = highlights_markdown(parsed)
    stats = parsed.get("stats") if isinstance(parsed.get("stats"), dict) else {}
    return library.apply_koreader_sidecar(
        item_id,
        percentage=percentage,
        progress=progress,
        status=status,
        highlights=highlights or None,
        stats_title=str(stats.get("title") or "").strip() or None,
        sidecar_name=upload_name,
    )


def is_progress_sidecar_name(name: str) -> bool:
    base = Path(name.replace("\\", "/")).name
    return bool(METADATA_LUA_RE.match(base))


def import_lua_bytes(
    name: str,
    data: bytes,
    *,
    archive_path: str | None = None,
    partial_index: dict[str, str] | None = None,
) -> dict | None:
    """Apply sidecar when it matches a registered book; otherwise None (quiet skip)."""
    try:
        text = data.decode("utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"Cannot read {name}: {exc}") from exc
    parsed = parse_metadata_lua(text)
    if parsed.get("percent_finished") is None and not parsed.get("last_xpointer") and not parsed.get("page"):
        return None
    item_id = match_registered_item(
        parsed,
        name,
        archive_path=archive_path,
        partial_index=partial_index,
    )
    if not item_id:
        return None
    return apply_sidecar(item_id, parsed, upload_name=name)


def import_upload(paths: list[Path]) -> dict:
    partial_index = library.ensure_all_registered_digests()
    results: list[dict] = []
    errors: list[dict] = []
    skipped: list[str] = []

    def handle_lua(display_name: str, data: bytes, archive_path: str | None = None) -> None:
        if not is_progress_sidecar_name(display_name):
            skipped.append(display_name)
            return
        try:
            row = import_lua_bytes(
                display_name,
                data,
                archive_path=archive_path,
                partial_index=partial_index,
            )
            if row:
                results.append(row)
            else:
                skipped.append(display_name)
        except ValueError as exc:
            errors.append({"file": display_name, "error": str(exc)})

    for path in paths:
        name = path.name.lower()
        if name.endswith(".lua"):
            handle_lua(path.name, path.read_bytes(), archive_path=path.name)
            continue
        if name.endswith(".zip"):
            with zipfile.ZipFile(path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    inner = info.filename.replace("\\", "/")
                    base = Path(inner).name
                    if not base.lower().endswith(".lua"):
                        continue
                    if not is_progress_sidecar_name(base):
                        skipped.append(inner)
                        continue
                    handle_lua(base, zf.read(info), archive_path=inner)
    if not results and not skipped and not errors:
        raise ValueError(
            "No metadata.*.lua sidecars found (zip .sdr folders; skip custom_metadata.lua)"
        )
    return {
        "ok": True,
        "imported": len(results),
        "results": results,
        "errors": errors,
        "skipped": skipped,
        "digest_index_size": len(partial_index),
    }