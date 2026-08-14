#!/usr/bin/env bash
# CorpusSieve — report the state of downloaded dumps.
# Usage: ./qa/dump_status.sh

set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

EXPECTED=(
  pages-articles-multistream.xml.bz2
  pages-articles-multistream-index.txt.bz2
  page.sql.gz
  categorylinks.sql.gz
  linktarget.sql.gz
)

echo "=============================================="
echo " Dump status   $(date '+%Y-%m-%d %H:%M')"
echo "=============================================="

for dir in dumps/*/; do
  [ -d "$dir" ] || continue
  wiki=$(basename "$dir")
  case "$wiki" in qa_*) continue;; esac
  echo ""
  echo "── $wiki"

  if compgen -G "$dir*-latest-*" >/dev/null; then
    echo "   ⚠️  '-latest-' filenames present — CorpusSieve will reject these."
    echo "      Rename to <proj>-<YYYYMMDD>-* (see qa/FINDINGS.md #8)."
  fi

  missing=0
  for f in "${EXPECTED[@]}"; do
    hit=$(compgen -G "$dir*-$f" 2>/dev/null | head -1)
    if [ -n "$hit" ]; then
      sz=$(ls -lh "$hit" | awk '{print $5}')
      printf "   %-46s %8s\n" "$(basename "$hit")" "$sz"
    else
      printf "   %-46s %8s\n" "(missing) *-$f" "--"
      missing=$((missing+1))
    fi
  done

  if pgrep -f "curl.*$wiki" >/dev/null 2>&1; then
    echo "   ⏳ a download is still in progress"
  elif [ "$missing" -eq 0 ]; then
    echo "   ✅ complete (run: ./qa/smoke_real_dump.sh $dir)"
  else
    echo "   ❌ $missing file(s) missing — run: ./qa/fetch_dumps.sh $wiki"
  fi
done

echo ""
echo "Disk free: $(df -h "$REPO" | tail -1 | awk '{print $4}')"
