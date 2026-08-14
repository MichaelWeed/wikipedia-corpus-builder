# CorpusSieve QA

Scripts for verifying CorpusSieve. Run from the repo root.

## Start here (morning checklist)

```bash
./qa/run_all_gates.sh
```
Runs every Definition-of-Done gate: engine lint/format/typecheck/tests, desktop
TypeScript + Rust, and committed-artifact drift. **Currently: 9/9 pass.**

```bash
./qa/smoke_real_dump.sh dumps/simplewiki
```
End-to-end against the real simplewiki dump already downloaded for you.
**Currently stops at step 2 with a known BLOCKER** — see `FINDINGS.md` #1.
That halt is the script working correctly, not a script bug.

## Read this next

**`FINDINGS.md`** — 8 findings from the security review and the first-ever run
against real Wikipedia data. All reproduced empirically. The headline:

> **CorpusSieve ingests zero category data from current Wikimedia dumps.**
> MediaWiki removed `categorylinks.cl_to` in favour of `cl_target_id` →
> `linktarget`. The parser reads the old schema, so every row is silently
> skipped and category traversal — the core feature — cannot work on real data.
> All 116 tests pass because the fixtures use the retired schema.

The fix is proven viable: joining `cl_target_id → linktarget.lt_id` (ns 14)
recovered 13,628 subcategory edges and 82,379 memberships from the real dump.
`linktarget.sql.gz` is already downloaded for both wikis.

## Scripts

| Script | Purpose |
|---|---|
| `run_all_gates.sh` | All DoD gates. Exit 0 = green. |
| `smoke_real_dump.sh [dir]` | Real-dump pipeline: inspect → metadata → compile → preview → build → validate → export. Non-destructive; never purges. |
| `fetch_dumps.sh <wiki> [date]` | Download a dump set with correct **dated** filenames. |

## Downloaded data

`dumps/` is gitignored. Already present:

- `dumps/simplewiki/` — complete 5-file set, ~470 MB, integrity-verified.
- `dumps/enwiki/` — full English Wikipedia, ~31 GB, downloaded overnight.

Files are named `<proj>-<YYYYMMDD>-*`, **not** `-latest-`. CorpusSieve's parser
requires a `YYYYMMDD` date, and a fixed date is required for source-fingerprint
reproducibility (design §9.3). `fetch_dumps.sh` handles this; the old runbook in
`docs/ACCEPTANCE_V0_1.md` did not (FINDINGS #8).

## Purge testing — read before running

Purge is the only destructive operation. **Do not run it against
`dumps/enwiki/` or `dumps/simplewiki/`** — findings #2, #3 and #4 are open, and
#4 means purge enrolls *every* file under the source directory for deletion,
not just dump files. Test it only against a throwaway copy.
