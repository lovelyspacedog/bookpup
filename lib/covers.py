"""Cover image validation and storage."""

from __future__ import annotations

from pathlib import Path

from . import user_paths

COVER_MAX_BYTES = 2 * 1024 * 1024
COVER_UPLOAD_MAX_BYTES = COVER_MAX_BYTES + 512 * 1024
COVER_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp"})


def detect_format(data: bytes) -> str:
    if len(data) < 32:
        raise ValueError("Cover file too small")
    if len(data) > COVER_MAX_BYTES:
        raise ValueError(f"Cover too large (max {COVER_MAX_BYTES // (1024 * 1024)} MB)")
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise ValueError("Cover must be JPEG, PNG, or WebP")


def resolve_cover_path(item_id: str) -> Path | None:
    if not item_id:
        return None
    base = user_paths.covers_dir() / item_id
    for ext in ("jpg", "jpeg", "png", "webp"):
        path = base.with_suffix("." + ext)
        if path.is_file():
            return path
    legacy = user_paths.covers_dir() / f"{item_id}.jpg"
    if legacy.is_file():
        return legacy
    return None


def cover_mime(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")


def remove_covers(item_id: str) -> None:
    if not item_id:
        return
    for ext in COVER_EXTENSIONS:
        path = user_paths.covers_dir() / f"{item_id}.{ext}"
        if path.is_file():
            path.unlink()


def save_cover(item_id: str, data: bytes) -> Path:
    fmt = detect_format(data)
    ext = "jpg" if fmt == "jpg" else fmt
    remove_covers(item_id)
    user_paths.covers_dir().mkdir(parents=True, exist_ok=True)
    dest = user_paths.covers_dir() / f"{item_id}.{ext}"
    dest.write_bytes(data)
    return dest