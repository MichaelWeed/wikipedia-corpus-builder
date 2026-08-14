#!/usr/bin/env bash
# Build the engine as a standalone PyInstaller executable and place it where
# Tauri's `externalBin` bundling convention expects a sidecar binary:
#   apps/desktop/src-tauri/binaries/corpussieve-engine-<target-triple>[.exe]
#
# PyInstaller does not cross-compile: this must run natively on each target
# platform (matches the existing desktop.yml CI matrix, which already runs
# one job per OS). Usage:
#   engine/scripts/build_sidecar.sh                  # host triple, from `rustc -vV`
#   engine/scripts/build_sidecar.sh <target-triple>   # explicit override
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENGINE_DIR="$REPO_ROOT/engine"
BIN_DIR="$REPO_ROOT/apps/desktop/src-tauri/binaries"

TARGET_TRIPLE="${1:-}"
if [ -z "$TARGET_TRIPLE" ]; then
  if ! command -v rustc >/dev/null 2>&1; then
    echo "error: no target triple given and rustc not found to infer the host triple" >&2
    exit 1
  fi
  TARGET_TRIPLE="$(rustc -vV | awk '/^host:/ { print $2 }')"
fi

EXE_SUFFIX=""
case "$TARGET_TRIPLE" in
  *windows*) EXE_SUFFIX=".exe" ;;
esac

echo "Building sidecar for target triple: $TARGET_TRIPLE"

cd "$ENGINE_DIR"
uv sync --group packaging
uv run --group packaging pyinstaller \
  --name corpussieve-engine \
  --onefile \
  --console \
  --clean \
  --noconfirm \
  --distpath dist/sidecar \
  --workpath build/pyinstaller \
  --specpath build/pyinstaller \
  -p src \
  src/corpussieve/cli/main.py

mkdir -p "$BIN_DIR"
DEST="$BIN_DIR/corpussieve-engine-${TARGET_TRIPLE}${EXE_SUFFIX}"
cp "dist/sidecar/corpussieve-engine${EXE_SUFFIX}" "$DEST"
chmod +x "$DEST"
echo "Sidecar binary ready at: $DEST"
