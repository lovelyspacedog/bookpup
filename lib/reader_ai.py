"""Summaries and Q&A grounded in reader excerpts."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from .core import CONFIG_DIR, load_config
from . import epub_text
from . import llama_local

CACHE_DIR = CONFIG_DIR / "ai-cache"
_rate_lock = threading.Lock()
_rate_buckets: dict[str, list[float]] = {}
RATE_LIMIT_PER_HOUR = 30


def _config_ai() -> dict:
    cfg = load_config()
    return {
        "n_ctx": int(cfg.get("ai_n_ctx") or 4096),
        "max_input_chars": int(cfg.get("ai_max_input_chars") or 4500),
        "max_output_tokens": int(cfg.get("ai_max_output_tokens") or 512),
        "prompt_version": int(cfg.get("ai_prompt_version") or 1),
        "model_id": Path(str(cfg.get("ai_model_path") or "unknown")).name,
    }


def _excerpt_char_limit(cfg: dict) -> int:
    """Keep excerpt + system instructions inside llama-server context."""
    n_ctx = int(cfg.get("n_ctx") or 4096)
    max_out = int(cfg.get("max_output_tokens") or 512)
    cap = int(cfg.get("max_input_chars") or 4500)
    # tokens reserved for prompts beyond raw excerpt (~chars/3)
    prompt_budget = max(256, n_ctx - max_out - 350)
    derived = prompt_budget * 3
    return max(epub_text.MIN_EXCERPT_CHARS * 2, min(cap, derived))


def check_rate_limit(client_key: str) -> None:
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets.setdefault(client_key, [])
        cutoff = now - 3600
        bucket[:] = [t for t in bucket if t >= cutoff]
        if len(bucket) >= RATE_LIMIT_PER_HOUR:
            raise PermissionError("AI rate limit exceeded (try again later)")
        bucket.append(now)


def cache_key(item_id: str, chapter_key: str, mode: str) -> str:
    cfg = _config_ai()
    raw = f"{item_id}|{chapter_key}|{mode}|v{cfg['prompt_version']}|{cfg['model_id']}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_read(key_hash: str) -> str | None:
    path = CACHE_DIR / f"{key_hash}.json"
    if not path.is_file():
        return None
    try:
        row = json.loads(path.read_text())
        return str(row.get("text") or "") or None
    except (json.JSONDecodeError, OSError):
        return None


def _cache_write(key_hash: str, text: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key_hash}.json"
    path.write_text(json.dumps({"text": text, "created_at": time.time()}, indent=2) + "\n")


def require_ai_enabled() -> None:
    ready = llama_local.ai_ready()
    if not ready["enabled"]:
        raise PermissionError(
            "Study is disabled on the server (set ai_enabled or run install_reader_ai.sh)."
        )
    if not ready["binary_present"] or not ready["model_loaded"]:
        raise FileNotFoundError(
            "Study is not installed on the server (run install_reader_ai.sh)."
        )


def excerpt_from_request(
    file_path: Path,
    body: dict,
) -> tuple[str, str, int]:
    fmt = str(body.get("format") or file_path.suffix.lstrip(".")).lower()
    cfg = _config_ai()
    spine_index = body.get("spine_index")
    if spine_index is not None:
        spine_index = int(spine_index)
    href = str(body.get("href") or "").strip() or None
    offset = body.get("offset")
    if offset is not None:
        offset = int(offset)
    max_chars = _excerpt_char_limit(cfg)
    key, text, n = epub_text.extract_excerpt(
        file_path,
        fmt,
        spine_index=spine_index,
        href=href,
        offset=offset,
        max_chars=max_chars,
    )
    if n < epub_text.MIN_EXCERPT_CHARS:
        raise ValueError("Not enough text in this section to summarize")
    return key, text, n


SUMMARIZE_SYSTEM = (
    "You summarize book excerpts for a reader. Use ONLY the excerpt below. "
    "Output: (1) bullet outline of key points, (2) 2-3 sentence takeaway. "
    "Do not invent plot beyond the excerpt."
)

ASK_SYSTEM = (
    "You answer reading-comprehension questions. Use ONLY the excerpt below. "
    "If the answer is not supported by the excerpt, say you cannot tell from this section. "
    "Keep answers concise."
)


def summarize(item_id: str, excerpt_key: str, excerpt: str, *, client_key: str) -> dict:
    require_ai_enabled()
    check_rate_limit(client_key)
    cfg = _config_ai()
    kh = cache_key(item_id, excerpt_key, "summarize")
    cached = _cache_read(kh)
    if cached:
        return {
            "ok": True,
            "summary": cached,
            "cached": True,
            "excerpt_chars": len(excerpt),
            "chapter_key": excerpt_key,
        }
    messages = [
        {"role": "system", "content": SUMMARIZE_SYSTEM},
        {"role": "user", "content": f"Excerpt:\n\n{excerpt}\n\nSummarize this section."},
    ]
    summary = llama_local.chat(messages, max_tokens=cfg["max_output_tokens"], timeout=180.0)
    _cache_write(kh, summary)
    return {
        "ok": True,
        "summary": summary,
        "cached": False,
        "excerpt_chars": len(excerpt),
        "chapter_key": excerpt_key,
    }


def ask(
    item_id: str,
    excerpt_key: str,
    excerpt: str,
    question: str,
    history: list[dict] | None,
    *,
    client_key: str,
) -> dict:
    require_ai_enabled()
    check_rate_limit(client_key)
    q = str(question or "").strip()
    if not q:
        raise ValueError("question required")
    if len(q) > 2000:
        raise ValueError("question too long")
    cfg = _config_ai()
    kh = cache_key(item_id, excerpt_key, f"ask:{hashlib.sha256(q.encode()).hexdigest()[:16]}")
    cached = _cache_read(kh)
    if cached:
        return {
            "ok": True,
            "answer": cached,
            "cached": True,
            "excerpt_chars": len(excerpt),
            "chapter_key": excerpt_key,
        }
    messages: list[dict] = [
        {"role": "system", "content": ASK_SYSTEM + f"\n\nExcerpt:\n\n{excerpt}"},
    ]
    for turn in (history or [])[-2:]:
        role = str(turn.get("role") or "user")
        if role not in ("user", "assistant"):
            role = "user"
        content = str(turn.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": q})
    answer = llama_local.chat(messages, max_tokens=min(384, cfg["max_output_tokens"]), timeout=180.0)
    _cache_write(kh, answer)
    return {
        "ok": True,
        "answer": answer,
        "cached": False,
        "excerpt_chars": len(excerpt),
        "chapter_key": excerpt_key,
    }


def status() -> dict:
    row = llama_local.ai_ready()
    row["ok"] = True
    return row