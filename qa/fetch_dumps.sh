#!/usr/bin/env bash
# CorpusSieve — download a Wikimedia dump set in the layout CorpusSieve expects.
#
#   ./qa/fetch_dumps.sh simplewiki          # ~470 MB  (recommended for QA)
#   ./qa/fetch_dumps.sh enwiki              # ~31 GB   (full English Wikipedia)
#   ./qa/fetch_dumps.sh simplewiki 20260801 # pin an explicit dump date
#
# IMPORTANT: files are saved with the DATED name (<proj>-<YYYYMMDD>-*), never
# "-latest-". CorpusSieve's filename parser requires a YYYYMMDD date, and a
# stable date is required for the source-fingerprint reproducibility guarantee
# (design §9.3). See qa/FINDINGS.md #8.
#
# Downloads are sequential and resumable (curl -C -), which is also the polite
# way to use dumps.wikimedia.org.

set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WIKI="${1:-simplewiki}"
DATE="${2:-}"
BASE="https://dumps.wikimedia.org"
DEST="$REPO/dumps/$WIKI"

# The 5 files CorpusSieve needs. linktarget is REQUIRED by current dumps:
# categorylinks no longer stores category names (see qa/FINDINGS.md #1).
FILES=(
  pages-articles-multistream.xml.bz2
  pages-articles-multistream-index.txt.bz2
  page.sql.gz
  categorylinks.sql.gz
  linktarget.sql.gz
)

if [ -z "$DATE" ]; then
  echo "Resolving newest dated dump for $WIKI ..."
  DATE=$(curl -s "$BASE/$WIKI/" | grep -oE '[0-9]{8}' | sort -u | tail -1)
  [ -n "$DATE" ] || { echo "Could not resolve a dump date for $WIKI"; exit 1; }
fi
echo "Using dump date: $DATE"

mkdir -p "$DEST"
cd "$DEST" || exit 1

TOTAL=0
for f in "${FILES[@]}"; do
  url="$BASE/$WIKI/$DATE/$WIKI-$DATE-$f"
  # Fall back to /latest/ if the dated dir has been rotated away.
  if ! curl -sIfL -o /dev/null "$url"; then
    echo "  (dated file unavailable, falling back to /latest/ for $f)"
    url="$BASE/$WIKI/latest/$WIKI-latest-$f"
  fi
  sz=$(curl -sIL "$url" | grep -i '^content-length:' | tail -1 | tr -d '\r' | awk '{print $2}')
  hr=$([ -n "${sz:-}" ] && echo "$sz" | awk '{printf "%.1f MB", $1/1024/1024}' || echo "?")
  echo "→ $WIKI-$DATE-$f  ($hr)"
  curl -# -L -C - --retry 5 --retry-delay 10 --retry-all-errors \
    -o "$WIKI-$DATE-$f" "$url" || { echo "  download failed: $f"; exit 1; }
done

echo ""
echo "Verifying archive integrity ..."
for f in "$WIKI-$DATE"-*.bz2; do [ -e "$f" ] && { bzip2 -t "$f" && echo "  ok  $f"; }; done
for f in "$WIKI-$DATE"-*.gz;  do [ -e "$f" ] && { gzip  -t "$f" && echo "  ok  $f"; }; done

echo ""
echo "Done. Files in $DEST:"
ls -lh
echo ""
echo "Next:  ./qa/smoke_real_dump.sh dumps/$WIKI"
