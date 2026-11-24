#!/usr/bin/env bash
# Install llama-server + Qwen2.5-0.5B-Instruct GGUF for BookPup reader AI (CPU / low RAM).
set -euo pipefail

APP_DIR="${BOOKPUP_APP_DIR:-$HOME/bookpup}"
BIN_DIR="$APP_DIR/bin"
MODEL_DIR="${BOOKPUP_CONFIG:-$HOME/.config/bookpup}/models"
CONFIG_FILE="${BOOKPUP_CONFIG:-$HOME/.config/bookpup}/config.json"
MODEL_NAME="qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_URL="${BOOKPUP_AI_MODEL_URL:-https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf}"
LLAMA_RELEASE="${BOOKPUP_LLAMA_RELEASE:-b7569}"
LLAMA_REPO="${BOOKPUP_LLAMA_REPO:-ggml-org/llama.cpp}"
ENABLE=0

usage() {
  cat <<EOF
Usage: $0 [-y]

  Installs llama.cpp runtime to $APP_DIR/llama-runtime/ and downloads ~400MB GGUF to $MODEL_DIR.
  Pass -y to set ai_enabled: true in $CONFIG_FILE (after files are present).
EOF
}

while getopts ":yh" opt; do
  case "$opt" in
    y) ENABLE=1 ;;
    h) usage; exit 0 ;;
    *) usage; exit 1 ;;
  esac
done

arch="$(uname -m)"
case "$arch" in
  x86_64) LLAMA_PLATFORM="ubuntu-x64" ;;
  aarch64|arm64)
    echo "BookPup reader AI: prebuilt llama.cpp for generic arm64 is not bundled." >&2
    echo "Set BOOKPUP_LLAMA_RELEASE and install a matching asset manually, or use x86_64 Expedition." >&2
    exit 1
    ;;
  *)
    echo "unsupported architecture: $arch (need x86_64)" >&2
    exit 1
    ;;
esac

mkdir -p "$BIN_DIR" "$MODEL_DIR"

llama_asset_name() {
  local tag="$1"
  printf 'llama-%s-bin-%s.tar.gz' "$tag" "$LLAMA_PLATFORM"
}

fetch_llama_tgz() {
  local tag="$1"
  local tgz url
  tgz="$(llama_asset_name "$tag")"
  url="https://github.com/${LLAMA_REPO}/releases/download/${tag}/${tgz}"
  if curl -fL --retry 3 --connect-timeout 30 -o "$TMP/llama.tgz" "$url"; then
    echo "Fetched $url"
    return 0
  fi
  return 1
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading llama.cpp ${LLAMA_RELEASE} (${LLAMA_PLATFORM})..."
if ! fetch_llama_tgz "$LLAMA_RELEASE"; then
  echo "Release ${LLAMA_RELEASE} failed; scanning recent tags for ${LLAMA_PLATFORM}..." >&2
  FOUND="$(curl -fsSL "https://api.github.com/repos/${LLAMA_REPO}/releases?per_page=40" |
    python3 -c "
import json, sys
plat = sys.argv[1]
for rel in json.load(sys.stdin):
  tag = rel.get('tag_name', '')
  for a in rel.get('assets') or []:
    n = a.get('name', '')
    if f'-bin-{plat}.tar.gz' in n and n.startswith('llama-'):
      print(tag)
      raise SystemExit(0)
" "$LLAMA_PLATFORM" 2>/dev/null || true)"
  if [[ -z "$FOUND" ]]; then
    echo "No ${LLAMA_PLATFORM} binary found. Pick a tag from https://github.com/${LLAMA_REPO}/releases" >&2
    echo "Example: BOOKPUP_LLAMA_RELEASE=b7569 $0" >&2
    exit 1
  fi
  LLAMA_RELEASE="$FOUND"
  echo "Trying tag ${LLAMA_RELEASE}..."
  if ! fetch_llama_tgz "$LLAMA_RELEASE"; then
    exit 1
  fi
fi

tar -xzf "$TMP/llama.tgz" -C "$TMP"
RUNTIME_DIR="$APP_DIR/llama-runtime"
ROOT="$(find "$TMP" -maxdepth 1 -type d -name 'llama-*' 2>/dev/null | head -n1)"
if [[ -z "$ROOT" ]]; then
  ROOT="$TMP"
fi
rm -rf "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR"
cp -a "$ROOT"/. "$RUNTIME_DIR/"
chmod +x "$RUNTIME_DIR"/llama-server 2>/dev/null || true
SRV="$RUNTIME_DIR/llama-server"
if [[ ! -x "$SRV" ]]; then
  echo "llama-server not found in archive" >&2
  exit 1
fi
# Ubuntu release bundles .so next to binaries; loader needs this directory.
export LD_LIBRARY_PATH="$RUNTIME_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
rm -f "$BIN_DIR/llama-server"
echo "Installed llama.cpp runtime at $RUNTIME_DIR"

MODEL_PATH="$MODEL_DIR/$MODEL_NAME"
if [[ -f "$MODEL_PATH" ]]; then
  echo "Model already present: $MODEL_PATH"
else
  echo "Downloading model (this may take a while)..."
  curl -fL --retry 3 --connect-timeout 30 -o "$MODEL_PATH" "$MODEL_URL"
fi
ls -lh "$MODEL_PATH"

PORT=18479
echo "Smoke test (llama-server + one completion)..."
"$SRV" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -m "$MODEL_PATH" \
  -c 4096 \
  -t 2 \
  -ngl 0 \
  >/tmp/bookpup-llama-smoke.log 2>&1 &
LPID=$!
sleep 8
if ! kill -0 "$LPID" 2>/dev/null; then
  echo "llama-server exited during smoke test; log:" >&2
  tail -n 40 /tmp/bookpup-llama-smoke.log >&2 || true
  exit 1
fi
HTTP="$(curl -sS -o "$TMP/out.json" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen","messages":[{"role":"user","content":"Say hi in three words."}],"max_tokens":16}' \
  "http://127.0.0.1:${PORT}/v1/chat/completions" || echo 000)"
kill "$LPID" 2>/dev/null || true
wait "$LPID" 2>/dev/null || true

if [[ "$HTTP" != "200" ]]; then
  echo "Smoke completion HTTP $HTTP; response:" >&2
  cat "$TMP/out.json" >&2 || true
  exit 1
fi
echo "Smoke test OK."

python3 - "$CONFIG_FILE" "$SRV" "$MODEL_PATH" "$ENABLE" <<'PY'
import json
import sys
from pathlib import Path

config_path, llama_bin, model_path, enable = sys.argv[1:5]
enable = enable == "1"
path = Path(config_path)
path.parent.mkdir(parents=True, exist_ok=True)
data = {}
if path.is_file():
    data = json.loads(path.read_text())
data.setdefault("ai_listen_port", 18479)
data.setdefault("ai_n_ctx", 4096)
data.setdefault("ai_max_input_chars", 4500)
data.setdefault("ai_max_output_tokens", 512)
data.setdefault("ai_prompt_version", 1)
data["ai_llama_bin"] = llama_bin
data["ai_model_path"] = model_path
if enable:
    data["ai_enabled"] = True
else:
    data.setdefault("ai_enabled", False)
path.write_text(json.dumps(data, indent=2) + "\n")
print(f"Updated {path} (ai_enabled={data.get('ai_enabled')})")
if not enable:
    print("Re-run with -y to enable ai_enabled after you are ready.")
PY

echo "Done. Reader AI uses lazy llama-server start from BookPup when ai_enabled is true."