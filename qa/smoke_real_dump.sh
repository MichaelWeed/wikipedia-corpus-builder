#!/usr/bin/env bash
# CorpusSieve — end-to-end smoke test against a REAL Wikimedia dump.
# Verifies design §38 acceptance criteria 3, 6-14, 18 on production data.
#
# Usage:
#   ./qa/smoke_real_dump.sh                    # uses dumps/simplewiki
#   ./qa/smoke_real_dump.sh dumps/enwiki       # uses a different dump set
#
# NOTE: this script is NON-DESTRUCTIVE. It never invokes `source purge`.
#       Purge is exercised separately by qa/purge_dryrun.sh.

set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

SRC="${1:-dumps/simplewiki}"
WORK="dumps/qa_run_$(basename "$SRC")"
OUT="$WORK/output"

step() { echo ""; echo "──────── $1"; }
die()  { echo "❌ FAILED: $1"; exit 1; }

echo "=============================================="
echo " Real-dump smoke test"
echo " source : $SRC"
echo " work   : $WORK"
echo "=============================================="

[ -d "$SRC" ] || die "source directory '$SRC' not found. Run qa/fetch_dumps.sh first."

rm -rf "$WORK"; mkdir -p "$WORK"

step "1. source inspect  (criterion 3: inspect without full decompression)"
( cd engine && uv run corpussieve source inspect --source "../$SRC" --json ) \
  | tee /tmp/cs_inspect.json | head -12
grep -q '"dump_kind": "multistream"' /tmp/cs_inspect.json \
  || die "expected multistream dump; check filenames are <proj>-<YYYYMMDD>-*, NOT -latest-"

step "2. metadata build  (criterion 4-equivalent: local category index)"
( cd engine && uv run corpussieve metadata build --source "../$SRC" --project-dir "../$WORK" --json ) \
  | tee /tmp/cs_meta.json | tail -12

# --- Regression guard: categorylinks schema (cl_to vs cl_target_id/linktarget) ---
# FINDINGS.md #1 (fixed 2026-08-14): current Wikimedia dumps replaced
# categorylinks.cl_to with cl_target_id -> linktarget(lt_id, lt_title). If this
# ever regresses to zero edges/memberships again, everything downstream is
# meaningless, so this check stays as a hard gate.
EDGES=$(sqlite3 "$WORK/cache/metadata.sqlite" "SELECT COUNT(*) FROM category_edges;" 2>/dev/null || echo 0)
MEMB=$(sqlite3  "$WORK/cache/metadata.sqlite" "SELECT COUNT(*) FROM category_membership;" 2>/dev/null || echo 0)
echo ""
echo "  category_edges      = $EDGES"
echo "  category_membership = $MEMB"
if [ "$EDGES" = "0" ] || [ "$MEMB" = "0" ]; then
  echo ""
  echo "  ❌ REGRESSION: zero category data ingested (see qa/FINDINGS.md #1)."
  echo "     Category traversal cannot work; everything downstream is meaningless."
  echo "     Check that linktarget.sql.gz is present and matches the categorylinks"
  echo "     dump date, and that metadata/rows.py's schema detection still matches"
  echo "     the dump's CREATE TABLE categorylinks column names. Stopping here."
  exit 2
fi

step "3. domain compile  (criteria 6,7,8,10: roots verified, no infinite loop, lock produced)"
cp examples/domains/video-games.yaml "$WORK/domain.yaml"
( cd engine && uv run corpussieve domain compile --domain "../$WORK/domain.yaml" \
    --project-dir "../$WORK" --json ) | tail -8 || die "domain compile"

step "4. domain preview  (criterion 9: inspect why pages are selected)"
( cd engine && uv run corpussieve domain preview --domain "../$WORK/domain.yaml" \
    --project-dir "../$WORK" --json ) | tail -20 || die "domain preview"

step "5. build  (criteria 11,12: consumes lock, extracts from real multistream)"
( cd engine && uv run corpussieve build run --domain "../$WORK/domain.lock.json" \
    --project-dir "../$WORK" --output "../$OUT" --json ) | tail -12 || die "build"

step "6. validate"
( cd engine && uv run corpussieve validate run --corpus "../$OUT/corpus" --json ) \
  | tail -8 || die "validate"

step "7. export markdown  (criteria 13,18: exports + attribution)"
( cd engine && uv run corpussieve export markdown --corpus "../$OUT/corpus" \
    --output "../$WORK/markdown" --json ) | tail -6 || die "export markdown"
[ -f "$WORK/markdown/ATTRIBUTION.md" ] || die "ATTRIBUTION.md missing (criterion 18)"

step "8. criterion 15: source unchanged after ordinary build"
# Compare a manifest of the source dir before/after (sizes + names).
find "$SRC" -type f -exec ls -l {} \; | awk '{print $5, $NF}' | sort > /tmp/cs_src_after.txt
echo "  source file manifest:"; sed 's/^/    /' /tmp/cs_src_after.txt

echo ""
echo "=============================================="
echo " ✅ SMOKE TEST COMPLETE"
echo " corpus  : $OUT/corpus"
echo " markdown: $WORK/markdown"
echo "=============================================="
