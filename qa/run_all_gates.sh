#!/usr/bin/env bash
# CorpusSieve — full gate suite (engine + desktop + regeneration drift).
# Runs every Definition-of-Done gate from plan/00_OVERVIEW.md §7.
# Usage:  ./qa/run_all_gates.sh
# Exit:   0 = all gates pass, 1 = at least one gate failed.

set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PASS=0; FAIL=0
ok()   { echo "  ✅ PASS  $1"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ FAIL  $1"; FAIL=$((FAIL+1)); }
run()  { # run <label> <cmd...>
  local label="$1"; shift
  local logfile="$REPO/.cs_gate.log"
  if "$@" >"$logfile" 2>&1; then ok "$label"; else
    bad "$label"; echo "     ---- last 15 lines ----"; tail -15 "$logfile" | sed 's/^/     /'
  fi
}

echo "=============================================="
echo " CorpusSieve gate suite   $(date '+%Y-%m-%d %H:%M')"
echo "=============================================="

echo ""
echo "[1/3] Engine (Python)"
run "ruff check"          bash -c "cd engine && uv run ruff check ."
run "ruff format --check" bash -c "cd engine && uv run ruff format --check ."
run "mypy --strict"       bash -c "cd engine && uv run mypy src"
run "pytest"              bash -c "cd engine && uv run pytest -q"

echo ""
echo "[2/3] Desktop (TypeScript + Rust)"
if [ -f apps/desktop/package.json ]; then
  # tauri.conf.json declares bundle.externalBin (P6.2 packaging) -- Tauri's
  # build script fails *any* cargo build, including plain `cargo check`, if
  # that binary is missing, so it must exist before the Rust steps below.
  # Cached across gate runs (like .venv/node_modules): only the first run
  # pays the PyInstaller cost. Content stats matter less here than presence
  # -- `cargo test` below exercises the actual bundled binary for real.
  if ! ls apps/desktop/src-tauri/binaries/corpussieve-engine-* >/dev/null 2>&1; then
    run "build sidecar (first run only)" engine/scripts/build_sidecar.sh
  fi
  run "tsc --noEmit"    pnpm -C apps/desktop lint
  run "vitest"          pnpm -C apps/desktop test
  run "vite build"      pnpm -C apps/desktop build
  run "cargo check"     cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
  run "cargo test"      cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
else
  echo "  ⏭  SKIP  apps/desktop not present"
fi

echo ""
echo "[3/3] Committed-artifact drift (schemas + fixtures must regenerate byte-identically)"
( cd engine && uv run python scripts/export_schemas.py    >/dev/null 2>&1 )
( cd engine && uv run python tests/fixtures/generator.py  >/dev/null 2>&1 )
DRIFT="$(git status --porcelain -- schemas engine/tests/fixtures/fixwiki)"
if [ -z "$DRIFT" ]; then ok "no regeneration drift"; else
  bad "regeneration drift detected"; echo "$DRIFT" | sed 's/^/     /'
fi

echo ""
echo "=============================================="
echo " RESULT: $PASS passed, $FAIL failed"
echo "=============================================="
[ "$FAIL" -eq 0 ] || exit 1
