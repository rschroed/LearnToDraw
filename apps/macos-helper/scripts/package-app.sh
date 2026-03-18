#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.build/arm64-apple-macosx/debug"
BINARY_PATH="$BUILD_DIR/LearnToDrawCameraHelper"
ENTITLEMENTS_PATH="$BUILD_DIR/LearnToDrawCameraHelper-entitlement.plist"
INFO_PLIST_TEMPLATE="$ROOT_DIR/Resources/Info.plist"
APP_DIR="${1:-$ROOT_DIR/.build/LearnToDrawCameraHelper.app}"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"

if [[ ! -x "$BINARY_PATH" ]]; then
  echo "Helper binary not found at $BINARY_PATH. Run 'swift build' first." >&2
  exit 1
fi

mkdir -p "$MACOS_DIR"
cp "$BINARY_PATH" "$MACOS_DIR/LearnToDrawCameraHelper"
cp "$INFO_PLIST_TEMPLATE" "$CONTENTS_DIR/Info.plist"

codesign --force --sign - \
  --entitlements "$ENTITLEMENTS_PATH" \
  "$APP_DIR"

echo "$APP_DIR"
