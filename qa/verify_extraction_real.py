#!/usr/bin/env python
"""Verify the EXTRACTION layer against a real Wikimedia dump.

This is deliberately independent of the metadata/category layer (originally
blocked by qa/FINDINGS.md #1, fixed 2026-08-14). It proves the mechanism
behind design §38 criterion 12 — selective extraction from a real multistream
dump without decompressing the whole file — as a fast, standalone check that
doesn't require a full metadata build first.

Usage (from repo root):
    uv run --project engine python qa/verify_extraction_real.py [dumps/enwiki]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from corpussieve.extraction.multistream_index import group_selected, iter_index
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

INDEX_SAMPLE = 400_000


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    dump_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else repo / "dumps" / "enwiki"
    if not dump_dir.is_absolute():
        dump_dir = repo / dump_dir

    if not dump_dir.exists():
        print(f"FAIL: dump directory not found: {dump_dir}")
        print("      run ./qa/fetch_dumps.sh first")
        return 1

    idx = next(iter(dump_dir.glob("*-pages-articles-multistream-index.txt.bz2")), None)
    if idx is None:
        print(f"FAIL: no multistream index in {dump_dir}")
        return 1

    print(f"dump: {dump_dir}")

    print(f"\n1. Parsing multistream index (sampling {INDEX_SAMPLE:,} entries)...")
    t0 = time.time()
    seen = 0
    sample_ids: list[int] = []
    for entry in iter_index(idx):
        seen += 1
        if 1000 < seen <= 1003:
            sample_ids.append(entry.page_id)
        if seen >= INDEX_SAMPLE:
            break
    print(f"   parsed {seen:,} entries in {time.time() - t0:.1f}s")
    if not sample_ids:
        print("FAIL: index yielded no usable page ids")
        return 1

    print("\n2. Grouping selected ids into stream plans...")
    plan = group_selected(idx, set(sample_ids))
    print(f"   {len(sample_ids)} ids -> {len(plan.groups)} group(s), "
          f"{len(plan.missing_ids)} missing")
    if plan.missing_ids:
        print("FAIL: selected ids missing from index")
        return 1

    print("\n3. Extracting those pages from the compressed dump...")
    t0 = time.time()
    adapter = WikimediaXmlDumpAdapter(dump_dir)
    got = []
    for page in adapter.extract_selected_pages(set(sample_ids)):
        got.append(page)
        print(f"   id={page.page_id:<9} ns={page.namespace} "
              f"rev={page.revision_id:<12} {page.title[:38]:<40} "
              f"{len(page.wikitext):,} chars")
        if len(got) >= len(sample_ids):
            break
    dt = time.time() - t0

    if len(got) != len(sample_ids):
        print(f"\nFAIL: extracted {len(got)}/{len(sample_ids)} pages")
        return 1
    if not all(p.wikitext for p in got):
        print("\nFAIL: some pages returned empty wikitext")
        return 1

    print(f"\n✅ PASS — extracted {len(got)}/{len(sample_ids)} pages in {dt:.1f}s "
          f"without decompressing the full dump.")
    print("   (Criterion 12's extraction mechanism works on real data. See")
    print("    qa/smoke_real_dump.sh for the full pipeline including selection.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
