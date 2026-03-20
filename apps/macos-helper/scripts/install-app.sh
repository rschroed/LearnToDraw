#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_TARGET="/Applications/LearnToDrawCameraHelper.app"
OPEN_AFTER_INSTALL=0

usage() {
  cat <<'EOF'
Usage:
  ./scripts/install-app.sh [--open] [TARGET_APP_PATH]

Examples:
  ./scripts/install-app.sh
  ./scripts/install-app.sh --open
  ./scripts/install-app.sh ~/Applications/LearnToDrawCameraHelper.app

Notes:
  - Default install target is /Applications/LearnToDrawCameraHelper.app
  - If /Applications requires elevated privileges, rerun with sudo
EOF
}

TARGET_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --open)
      OPEN_AFTER_INSTALL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$TARGET_PATH" ]]; then
        echo "Unexpected extra argument: $1" >&2
        usage >&2
        exit 1
      fi
      TARGET_PATH="$1"
      shift
      ;;
  esac
done

TARGET_PATH="${TARGET_PATH:-$DEFAULT_TARGET}"
TARGET_PARENT="$(dirname "$TARGET_PATH")"
STAGING_PATH="$(mktemp -d)/LearnToDrawCameraHelper.app"

cleanup() {
  rm -rf "$(dirname "$STAGING_PATH")"
}
trap cleanup EXIT

"$ROOT_DIR/scripts/package-app.sh" "$STAGING_PATH" >/dev/null

mkdir -p "$TARGET_PARENT" 2>/dev/null || true

if [[ -e "$TARGET_PATH" ]] && [[ ! -w "$TARGET_PATH" ]] && [[ $EUID -ne 0 ]]; then
  echo "Cannot replace existing app at $TARGET_PATH without elevated privileges." >&2
  echo "Rerun with sudo or choose a writable target path." >&2
  exit 1
fi

if [[ ! -w "$TARGET_PARENT" ]] && [[ $EUID -ne 0 ]]; then
  echo "Cannot write to $TARGET_PARENT without elevated privileges." >&2
  echo "Rerun with sudo or choose a writable target path." >&2
  exit 1
fi

rm -rf "$TARGET_PATH"
ditto "$STAGING_PATH" "$TARGET_PATH"

echo "Installed helper app to $TARGET_PATH"

if [[ "$OPEN_AFTER_INSTALL" -eq 1 ]]; then
  open "$TARGET_PATH"
fi
