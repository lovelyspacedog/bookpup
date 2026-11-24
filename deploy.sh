#!/usr/bin/env bash
# Whatbox Expedition wrapper around scripts/deploy-remote.sh (sshpass + secret file).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SECRET="${EXPEDITION_SECRET:-$HOME/.ssh/expedition_secret}"
WOOFER_WWW="${WOOFER_WWW:-$HOME/Scripts/hyperwoofer/www}"

if [[ ! -f "$SECRET" ]]; then
  printf 'missing expedition secret: %s\n' "$SECRET" >&2
  exit 1
fi

mkdir -p "$ROOT/static/kennel/fonts"
if [[ -d "$WOOFER_WWW" ]]; then
  cp "$WOOFER_WWW/fonts/"*.woff2 "$ROOT/static/kennel/fonts/" 2>/dev/null || true
fi
if [[ ! -f "$ROOT/static/kennel/theme.css" ]]; then
  printf '/* minimal theme */\n' >"$ROOT/static/kennel/theme.css"
fi

export BOOKPUP_DEPLOY_HOST="${EXPEDITION_HOST:-tonypup@expedition.whatbox.ca}"
export BOOKPUP_DEPLOY_SECRET="$SECRET"
export BOOKPUP_DEPLOY_PUBLIC_URL_HINT="${BOOKPUP_DEPLOY_PUBLIC_URL_HINT:-https://bookpup.tonypup.box.ca}"
exec "$ROOT/scripts/deploy-remote.sh"