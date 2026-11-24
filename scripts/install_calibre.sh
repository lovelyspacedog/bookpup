#!/usr/bin/env bash
# Portable Calibre tarball into ~/calibre-bundle (headless ebook-convert).
set -euo pipefail
DEST="${CALIBRE_INSTALL_DIR:-$HOME/calibre-bundle}"
VER="${CALIBRE_VERSION:-7.26.0}"
ARCH="${CALIBRE_ARCH:-x86_64}"
CONVERT="$DEST/ebook-convert"

if [[ -x "$CONVERT" ]]; then
  echo "Calibre already installed at $DEST"
  "$CONVERT" --version | head -1
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
URL="https://download.calibre-ebook.com/${VER}/calibre-${VER}-${ARCH}.txz"
echo "Downloading $URL ..."
curl -fsSL -o "$TMP/calibre.txz" "$URL"
rm -rf "$DEST"
mkdir -p "$DEST"
tar xf "$TMP/calibre.txz" -C "$DEST"
if [[ ! -x "$CONVERT" ]]; then
  echo "ebook-convert not found in $DEST" >&2
  exit 1
fi
echo "Installed: $CONVERT"
"$CONVERT" --version | head -1