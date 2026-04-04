#!/usr/bin/env bash
# Install boil - automatically restore missing code from git history
# Usage:
#   curl -sSL https://raw.githubusercontent.com/mdonahoe/boiler/main/install.sh | bash
#   curl -sSL https://raw.githubusercontent.com/mdonahoe/boiler/main/install.sh | PREFIX=$HOME/.local bash

set -euo pipefail

REPO="mdonahoe/boiler"
INSTALL_DIR="${PREFIX:-/usr/local}/bin"

# Detect OS
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
case "$OS" in
  linux|darwin) ;;
  *) echo "Error: unsupported OS: $OS" >&2; exit 1 ;;
esac

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)        ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "Error: unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

# Resolve version
VERSION="${BOIL_VERSION:-}"
if [ -z "$VERSION" ]; then
  VERSION=$(curl -sSf "https://api.github.com/repos/${REPO}/releases/latest" \
    | grep '"tag_name"' | head -1 | cut -d'"' -f4)
fi
if [ -z "$VERSION" ]; then
  echo "Error: could not determine latest release version" >&2
  exit 1
fi

BINARY="boil-${OS}-${ARCH}"
URL="https://github.com/${REPO}/releases/download/${VERSION}/${BINARY}"

echo "Installing boil ${VERSION} (${OS}/${ARCH}) to ${INSTALL_DIR}..."

# Download
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
curl -sSfL "$URL" -o "$TMP"

# Verify checksum if sha256sum is available
if command -v sha256sum &>/dev/null; then
  CHECKSUMS_URL="https://github.com/${REPO}/releases/download/${VERSION}/checksums.txt"
  EXPECTED=$(curl -sSfL "$CHECKSUMS_URL" | grep "$BINARY" | awk '{print $1}')
  ACTUAL=$(sha256sum "$TMP" | awk '{print $1}')
  if [ "$EXPECTED" != "$ACTUAL" ]; then
    echo "Error: checksum mismatch" >&2
    echo "  expected: $EXPECTED" >&2
    echo "  actual:   $ACTUAL" >&2
    exit 1
  fi
fi

# Install
chmod +x "$TMP"
if [ -w "$INSTALL_DIR" ]; then
  mv "$TMP" "${INSTALL_DIR}/boil"
else
  sudo mv "$TMP" "${INSTALL_DIR}/boil"
fi

echo "Installed: $(command -v boil || echo "${INSTALL_DIR}/boil")"
boil --version 2>/dev/null || true
