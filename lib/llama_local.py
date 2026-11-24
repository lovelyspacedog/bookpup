"""Local llama-server process and OpenAI-compatible chat client."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .core import CONFIG_DIR, load_config

_lock = threading.Lock()
_infer_lock = threading.Lock()
_server_lock = threading.Lock()
PIDFILE = CONFIG_DIR / "llama.pid"


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def _subprocess_env(binary: Path) -> dict[str, str]:
    """llama.cpp release tarballs ship .so files beside llama-server."""
    env = os.environ.copy()
    lib_dir = str(binary.parent)
    prev = env.get("LD_LIBRARY_PATH", "")
    if prev:
        if lib_dir not in prev.split(":"):
            env["LD_LIBRARY_PATH"] = f"{lib_dir}:{prev}"
    else:
        env["LD_LIBRARY_PATH"] = lib_dir
    return env


def ai_settings() -> dict:
    cfg = load_config()
    enabled_env = os.environ.get("BOOKPUP_AI_ENABLED", "").strip().lower()
    if enabled_env in ("1", "true", "yes"):
        enabled = True
    elif enabled_env in ("0", "false", "no"):
        enabled = False
    else:
        enabled = bool(cfg.get("ai_enabled", False))
    model_path = os.environ.get("BOOKPUP_AI_MODEL_PATH") or str(cfg.get("ai_model_path") or "")
    default_bin = Path.home() / "bookpup" / "llama-runtime" / "llama-server"
    legacy_bin = Path.home() / "bookpup" / "bin" / "llama-server"
    fallback = default_bin if default_bin.is_file() else legacy_bin
    llama_bin = os.environ.get("BOOKPUP_AI_LLAMA_BIN") or str(cfg.get("ai_llama_bin") or fallback)
    port = int(cfg.get("ai_listen_port") or 18479)
    return {
        "enabled": enabled,
        "model_path": model_path,
        "llama_bin": llama_bin,
        "port": port,
        "n_ctx": int(cfg.get("ai_n_ctx") or 4096),
        "max_output_tokens": int(cfg.get("ai_max_output_tokens") or 512),
    }


def ai_ready() -> dict:
    st = ai_settings()
    model = _expand(st["model_path"]) if st["model_path"] else None
    binary = _expand(st["llama_bin"]) if st["llama_bin"] else None
    return {
        "enabled": st["enabled"],
        "model_loaded": bool(model and model.is_file()),
        "binary_present": bool(binary and binary.is_file()),
        "ready": st["enabled"] and bool(model and model.is_file()) and bool(binary and binary.is_file()),
        "queue_busy": _infer_lock.locked(),
        "port": st["port"],
    }


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid() -> int | None:
    if not PIDFILE.is_file():
        return None
    try:
        return int(PIDFILE.read_text().strip())
    except ValueError:
        return None


def _health(port: int, timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
            headers={"User-Agent": "BookPup/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        return exc.code != 503
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _model_accepts_inference(port: int, timeout: float = 5.0) -> bool:
    """True when chat/completions will not return 503 Loading model."""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/models",
            headers={"User-Agent": "BookPup/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode())
            return bool(data.get("data"))
    except urllib.error.HTTPError as exc:
        if exc.code == 503:
            return False
        return exc.code < 500
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return False


def wait_for_model(port: int, max_wait: float = 180.0) -> None:
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if _model_accepts_inference(port):
            return
        time.sleep(2.0)
    raise RuntimeError(
        "llama-server is still loading the model (large GGUF on shared CPU). Try again in a minute."
    )


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def ensure_server() -> None:
    st = ai_settings()
    if not st["enabled"]:
        raise RuntimeError("Study is disabled (set ai_enabled in config)")
    model = _expand(st["model_path"])
    binary = _expand(st["llama_bin"])
    if not model.is_file():
        raise FileNotFoundError(f"AI model missing: {model}")
    if not binary.is_file():
        raise FileNotFoundError(f"llama-server missing: {binary} (run scripts/install_reader_ai.sh)")

    port = st["port"]
    if _health(port) and _model_accepts_inference(port):
        return

    with _server_lock:
        if _health(port) and _model_accepts_inference(port):
            return
        pid = _read_pid()
        if pid and _pid_running(pid):
            if _port_open(port):
                wait_for_model(port, max_wait=180.0)
                return
        if PIDFILE.is_file():
            PIDFILE.unlink(missing_ok=True)

        log = CONFIG_DIR / "llama.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log_fd = open(log, "a", encoding="utf-8")
        proc = subprocess.Popen(
            [
                str(binary),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "-m",
                str(model),
                "-c",
                str(max(2048, min(8192, st["n_ctx"]))),
                "-t",
                "2",
                "-ngl",
                "0",
            ],
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=_subprocess_env(binary),
        )
        log_fd.close()
        PIDFILE.write_text(str(proc.pid))
        deadline = time.time() + 60
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("llama-server exited during startup (see llama.log)")
            if _port_open(port):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("llama-server did not open its port in time")
        wait_for_model(port, max_wait=180.0)


def chat(messages: list[dict], *, max_tokens: int | None = None, timeout: float = 180.0) -> str:
    st = ai_settings()
    if max_tokens is None:
        max_tokens = st["max_output_tokens"]
    port = st["port"]
    ensure_server()
    wait_for_model(port, max_wait=min(timeout, 180.0))
    body = json.dumps(
        {
            "model": "qwen",
            "messages": messages,
            "max_tokens": int(max_tokens),
            "temperature": 0.3,
        }
    ).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "BookPup/1.0"},
        method="POST",
    )
    with _infer_lock:
        deadline = time.time() + timeout
        data = None
        last_detail = ""
        while time.time() < deadline:
            try:
                remain = max(5.0, deadline - time.time())
                with urllib.request.urlopen(req, timeout=remain) as resp:
                    data = json.loads(resp.read().decode())
                break
            except urllib.error.HTTPError as exc:
                last_detail = exc.read().decode(errors="replace")
                if exc.code == 503 and "Loading model" in last_detail:
                    time.sleep(2.0)
                    if not _model_accepts_inference(port, timeout=2.0):
                        continue
                raise RuntimeError(f"llama-server HTTP {exc.code}: {last_detail[:200]}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"llama-server unreachable: {exc}") from exc
        if data is None:
            raise RuntimeError(
                "llama-server timed out while loading the model"
                + (f": {last_detail[:120]}" if last_detail else "")
            )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("empty completion from llama-server")
    msg = choices[0].get("message") or {}
    content = str(msg.get("content") or "").strip()
    if not content:
        raise RuntimeError("empty message content from llama-server")
    return content