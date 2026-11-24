#!/usr/bin/env bash
# Deploy BookPup to expedition and keep it running via crontab.
set -euo pipefail

HOST="${EXPEDITION_HOST:-tonypup@expedition.whatbox.ca}"
SECRET="${EXPEDITION_SECRET:-$HOME/.ssh/expedition_secret}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
WOOFER_WWW="${WOOFER_WWW:-$HOME/Scripts/hyperwoofer/www}"

if [[ ! -f "$SECRET" ]]; then
  printf 'missing expedition secret: %s\n' "$SECRET" >&2
  exit 1
fi
mode="$(stat -c '%a' "$SECRET" 2>/dev/null || stat -f '%OLp' "$SECRET")"
if [[ "$mode" != "600" && "$mode" != "400" ]]; then
  printf 'expedition secret must be mode 600 or 400 (currently %s)\n' "$mode" >&2
  exit 1
fi

mkdir -p "$ROOT/static/kennel/fonts"
if [[ -d "$WOOFER_WWW" ]]; then
  cp "$WOOFER_WWW/fonts/"*.woff2 "$ROOT/static/kennel/fonts/" 2>/dev/null || true
fi
if [[ ! -f "$ROOT/static/kennel/theme.css" ]]; then
  printf '/* minimal theme */\n' >"$ROOT/static/kennel/theme.css"
fi

export SSHPASS
SSHPASS="$(<"$SECRET")"
SSH_OPTS=(-4 -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20)

ssh_exp() {
  sshpass -e ssh "${SSH_OPTS[@]}" "$HOST" "$@"
}

chmod +x "$ROOT/start" "$ROOT/bookpup.py"

ssh_exp 'mkdir -p "$HOME/bookpup" "$HOME/.config/bookpup"'

rsync -a --delete --exclude __pycache__ --exclude tests --exclude .git \
  -e "sshpass -e ssh ${SSH_OPTS[*]}" \
  "$ROOT/bookpup.py" "$ROOT/start" "$ROOT/static" "$ROOT/lib" "$ROOT/scripts" "$ROOT/vendor" \
  "$HOST:~/bookpup/"

ssh_exp 'chmod +x "$HOME/bookpup/start" "$HOME/bookpup/bookpup.py" "$HOME/bookpup/scripts/install_calibre.sh" "$HOME/bookpup/scripts/install_reader_ai.sh" 2>/dev/null || true'
ssh_exp 'cd "$HOME/bookpup" && python3 -c "import lib.server"' || {
  printf 'lib.server failed to import on %s\n' "$HOST" >&2
  exit 1
}

ssh_exp 'bash -s' <<'REMOTE'
set -euo pipefail
tmp="$(mktemp)"
crontab -l 2>/dev/null >"$tmp" || true
if ! grep -q 'bookpup/start' "$tmp"; then
  printf '%s\n' \
    '@reboot /home/tonypup/bookpup/start' \
    '*/5 * * * * /home/tonypup/bookpup/start' >>"$tmp"
  crontab "$tmp"
fi
rm -f "$tmp"
if pgrep -f '/home/tonypup/bookpup/bookpup.py' >/dev/null 2>&1; then
  pkill -f '/home/tonypup/bookpup/bookpup.py' || true
  rm -f "$HOME/.config/bookpup/bookpup.pid"
  sleep 1
fi
pkill -f 'llama-runtime/llama-server' 2>/dev/null || true
rm -f "$HOME/.config/bookpup/llama.pid"
if [[ ! -x "$HOME/calibre-bundle/ebook-convert" ]] && [[ -x "$HOME/bookpup/scripts/install_calibre.sh" ]]; then
  echo "Installing Calibre to ~/calibre (one-time, may take a few minutes)..." >&2
  if ! bash "$HOME/bookpup/scripts/install_calibre.sh"; then
    echo "warning: Calibre install failed; MOBI/AZW Read will not work until install_calibre.sh succeeds" >&2
  fi
fi
/home/tonypup/bookpup/start
REMOTE

echo "Deployed BookPup to $HOST (127.0.0.1:18478)."
ssh_exp 'curl -fsS "http://127.0.0.1:18478/api/health" >/dev/null && echo "Health OK: http://127.0.0.1:18478/api/health" || echo "warning: /api/health check failed (is BookPup up?)"' || true
echo "Whatbox custom app: name BookPup, port 18478 → https://bookpup.tonypup.box.ca"
if sshpass -e ssh "${SSH_OPTS[@]}" "$HOST" 'test -f "$HOME/.config/bookpup/config.json"'; then
  echo "Config exists on VPS; password is in ~/.config/bookpup/config.json"
else
  echo "First run created password on VPS in ~/.config/bookpup/config.json"
fi