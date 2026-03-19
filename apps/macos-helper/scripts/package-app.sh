#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/.build/arm64-apple-macosx/debug"
BINARY_PATH="$BUILD_DIR/LearnToDrawCameraHelper"
ENTITLEMENTS_PATH="$BUILD_DIR/LearnToDrawCameraHelper-entitlement.plist"
INFO_PLIST_TEMPLATE="$ROOT_DIR/Resources/Info.plist"
APP_DIR="${1:-$ROOT_DIR/dist/LearnToDrawCameraHelper.app}"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
CONFIG_PATH="$RESOURCES_DIR/LearnToDrawHelperConfig.json"

if [[ ! -x "$BINARY_PATH" ]]; then
  echo "Helper binary not found at $BINARY_PATH. Run 'swift build' first." >&2
  exit 1
fi

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"
cp "$BINARY_PATH" "$MACOS_DIR/LearnToDrawCameraHelper"
cp "$INFO_PLIST_TEMPLATE" "$CONTENTS_DIR/Info.plist"
cat > "$CONFIG_PATH" <<EOF
{
  "repoRoot": "$REPO_ROOT",
  "backendHost": "127.0.0.1",
  "backendPort": 8000,
  "helperHost": "127.0.0.1",
  "helperPort": 8001
}
EOF

codesign --force --sign - \
  --entitlements "$ENTITLEMENTS_PATH" \
  "$APP_DIR"

echo "$APP_DIR"
