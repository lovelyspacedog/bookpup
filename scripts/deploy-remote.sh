#!/usr/bin/env bash
# Deploy BookPup to a remote VPS (SSH key/agent default; optional sshpass via secret file).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${BOOKPUP_DEPLOY_HOST:-}"
SECRET="${BOOKPUP_DEPLOY_SECRET:-${EXPEDITION_SECRET:-}}"
SSH_OPTS_STR="${BOOKPUP_DEPLOY_SSH_OPTS:--4 -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20}"
# shellcheck disable=SC2206
SSH_OPTS=($SSH_OPTS_STR)

if [[ -z "$HOST" ]]; then
  printf 'BOOKPUP_DEPLOY_HOST is required (e.g. user@your.vps)\n' >&2
  exit 1
fi

USE_SSHPASS=0
if [[ -n "${SSHPASS:-}" ]]; then
  USE_SSHPASS=1
elif [[ -n "$SECRET" && -f "$SECRET" ]]; then
  mode="$(stat -c '%a' "$SECRET" 2>/dev/null || stat -f '%OLp' "$SECRET")"
  if [[ "$mode" != "600" && "$mode" != "400" ]]; then
    printf 'deploy secret must be mode 600 or 400 (currently %s): %s\n' "$mode" "$SECRET" >&2
    exit 1
  fi
  export SSHPASS
  SSHPASS="$(<"$SECRET")"
  USE_SSHPASS=1
fi

ssh_remote() {
  if [[ "$USE_SSHPASS" -eq 1 ]]; then
    sshpass -e ssh "${SSH_OPTS[@]}" "$HOST" "$@"
  else
    ssh "${SSH_OPTS[@]}" "$HOST" "$@"
  fi
}

rsync_remote() {
  local dest="$1"
  shift
  if [[ "$USE_SSHPASS" -eq 1 ]]; then
    rsync -a --delete -e "sshpass -e ssh ${SSH_OPTS[*]}" "$@" "$HOST:$dest"
  else
    rsync -a --delete -e "ssh ${SSH_OPTS[*]}" "$@" "$HOST:$dest"
  fi
}

REMOTE_HOME="${BOOKPUP_DEPLOY_REMOTE_HOME:-}"
if [[ -z "$REMOTE_HOME" ]]; then
  REMOTE_HOME="$(ssh_remote 'printf %s "$HOME"')"
fi

REMOTE_APP="${BOOKPUP_DEPLOY_APP_DIR:-$REMOTE_HOME/bookpup}"

chmod +x "$ROOT/start" "$ROOT/bookpup.py"

ssh_remote "mkdir -p \"$REMOTE_APP\" \"$REMOTE_HOME/.config/bookpup\""

rsync_remote "$REMOTE_APP/" \
  --exclude __pycache__ --exclude tests --exclude .git \
  "$ROOT/bookpup.py" "$ROOT/start" "$ROOT/static" "$ROOT/lib" "$ROOT/scripts" "$ROOT/vendor"

ssh_remote "chmod +x \"$REMOTE_APP/start\" \"$REMOTE_APP/bookpup.py\" \"$REMOTE_APP/scripts/install_calibre.sh\" \"$REMOTE_APP/scripts/install_reader_ai.sh\" 2>/dev/null || true"
ssh_remote "cd \"$REMOTE_APP\" && python3 -c \"import lib.server\"" || {
  printf 'lib.server failed to import on %s\n' "$HOST" >&2
  exit 1
}

CRON_START="${REMOTE_APP}/start"
CRON_LINE_BOOT="@reboot ${CRON_START}"
CRON_LINE_5="*/5 * * * * ${CRON_START}"
BK_PY="${REMOTE_APP}/bookpup.py"

ssh_remote "bash -s" <<REMOTE
set -euo pipefail
APP_DIR='${REMOTE_APP}'
CRON_START='${CRON_START}'
BK_PY='${BK_PY}'
tmp="\$(mktemp)"
crontab -l 2>/dev/null >"\$tmp" || true
if ! grep -q 'bookpup/start' "\$tmp"; then
  printf '%s\n' \
    '@reboot '\$CRON_START \
    '*/5 * * * * '\$CRON_START >>"\$tmp"
  crontab "\$tmp"
fi
rm -f "\$tmp"
if pgrep -f "\$BK_PY" >/dev/null 2>&1; then
  pkill -f "\$BK_PY" || true
  rm -f "\$HOME/.config/bookpup/bookpup.pid"
  sleep 1
fi
pkill -f 'llama-runtime/llama-server' 2>/dev/null || true
rm -f "\$HOME/.config/bookpup/llama.pid"
if [[ ! -x "\$HOME/calibre-bundle/ebook-convert" ]] && [[ -x "\$APP_DIR/scripts/install_calibre.sh" ]]; then
  echo "Installing Calibre to ~/calibre (one-time, may take a few minutes)..." >&2
  if ! bash "\$APP_DIR/scripts/install_calibre.sh"; then
    echo "warning: Calibre install failed; MOBI/AZW Read will not work until install_calibre.sh succeeds" >&2
  fi
fi
"\$CRON_START"
REMOTE

echo "Deployed BookPup to $HOST (127.0.0.1:18478 loopback)."
ssh_remote 'curl -fsS "http://127.0.0.1:18478/api/health" >/dev/null && echo "Health OK: http://127.0.0.1:18478/api/health" || echo "warning: /api/health check failed (is BookPup up?)"' || true
if [[ -n "${BOOKPUP_DEPLOY_PUBLIC_URL_HINT:-}" ]]; then
  echo "Public URL hint: set public_url in ~/.config/bookpup/config.json → ${BOOKPUP_DEPLOY_PUBLIC_URL_HINT}"
fi
if ssh_remote 'test -f "$HOME/.config/bookpup/config.json"'; then
  echo "Config exists on VPS; credentials in ~/.config/bookpup/config.json"
else
  echo "First run created credentials on VPS in ~/.config/bookpup/config.json"
fi