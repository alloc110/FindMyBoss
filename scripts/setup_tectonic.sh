#!/usr/bin/env bash
set -e

# Setup script for Tectonic LaTeX Engine
# Tectonic is a standalone, self-contained XeTeX engine (~30MB) that automatically downloads
# required packages and fonts on-demand without needing a 4GB TeXLive installation.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$PROJECT_ROOT/bin"
TECTONIC_BIN="$BIN_DIR/tectonic"

mkdir -p "$BIN_DIR"

if [ -f "$TECTONIC_BIN" ] && [ -x "$TECTONIC_BIN" ]; then
    echo "✅ Tectonic already installed at: $TECTONIC_BIN"
    "$TECTONIC_BIN" --version
    exit 0
fi

echo "⬇️ Downloading standalone Tectonic binary for Linux x86_64..."
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$TMP_DIR"
if curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh; then
    if [ -f "$TMP_DIR/tectonic" ]; then
        mv "$TMP_DIR/tectonic" "$TECTONIC_BIN"
        chmod +x "$TECTONIC_BIN"
        echo "✅ Successfully installed Tectonic at $TECTONIC_BIN"
        "$TECTONIC_BIN" --version
        exit 0
    fi
fi

# Fallback: Download tarball directly from GitHub Releases
echo "⚠️ Installer failed, falling back to direct GitHub release download..."
TECTONIC_VER="0.15.0"
URL="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VER}/tectonic-${TECTONIC_VER}-x86_64-unknown-linux-musl.tar.gz"

curl -sL "$URL" -o "$TMP_DIR/tectonic.tar.gz"
tar -xzf "$TMP_DIR/tectonic.tar.gz" -C "$TMP_DIR"
mv "$TMP_DIR/tectonic" "$TECTONIC_BIN"
chmod +x "$TECTONIC_BIN"

echo "✅ Successfully installed Tectonic to: $TECTONIC_BIN"
"$TECTONIC_BIN" --version
