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
End-to-end against the real simplewiki dump already downloaded for you:
inspect → metadata → compile → preview → build → validate → export.
**Currently completes successfully** — 3,372 real "video games" articles
selected, built, validated, and exported to Markdown.

## Read this next

**`FINDINGS.md`** — 9 findings from the security review and the first-ever
runs against real Wikipedia data. All reproduced empirically.

The headline finding (#1, **FIXED 2026-08-14**): CorpusSieve initially
ingested zero category data from current Wikimedia dumps — MediaWiki removed
`categorylinks.cl_to` in favour of `cl_target_id` → `linktarget`, and the
parser read the retired schema, so every categorylinks row was silently
skipped. Fixed by reading column names from each dump's own `CREATE TABLE`
statement (resilient to future schema drift, not just this one) and joining
through `linktarget` when needed. Verified end-to-end on real data; see
`FINDINGS.md` for before/after numbers and the new test coverage.

Two things still open and worth knowing before you dig in:
- **#2/#3** — purge's "Move to Trash" can silently perform a *permanent*
  delete, and the plan always reports `reversible: true` regardless. Data-loss
  risk, not yet fixed.
- **#9** — real Markdown exports have template artifacts leaking into the
  text (75% of simplewiki "video games" exports had normalization warnings).
  Extraction and selection are correct; this is a separate normalization
  (P5) quality bug.

## Scripts

| Script | Purpose |
|---|---|
| `run_all_gates.sh` | All DoD gates. Exit 0 = green. |
| `smoke_real_dump.sh [dir]` | Real-dump pipeline: inspect → metadata → compile → preview → build → validate → export. Non-destructive; never purges. |
| `fetch_dumps.sh <wiki> [date]` | Download a dump set with correct **dated** filenames. |
| `dump_status.sh` | Report which dump files are present, complete, or misnamed. |
| `verify_extraction_real.py` | Prove the extraction layer works on a real dump, independent of the metadata/category layer. |

## Downloaded data

`dumps/` is gitignored. Already present:

- `dumps/simplewiki/` — complete 5-file set, ~470 MB, integrity-verified.
  Full pipeline run: `dumps/qa_run_simplewiki/`.
- `dumps/enwiki/` — full English Wikipedia 20260801, **31 GB, all 5 files
  present and correctly dated**, integrity-verified. `source inspect` reads it
  in 0.21 s. `metadata build` against it will take considerably longer than
  simplewiki (proportional to its ~7x page count and ~3x categorylinks size)
  but is expected to work now that FINDINGS #1 is fixed — not yet run end-to-end
  as part of this QA pass.

Files are named `<proj>-<YYYYMMDD>-*`, **not** `-latest-`. CorpusSieve's parser
requires a `YYYYMMDD` date, and a fixed date is required for source-fingerprint
reproducibility (design §9.3). `fetch_dumps.sh` handles this; the old runbook in
`docs/ACCEPTANCE_V0_1.md` did not (FINDINGS #8, also fixed).

## Purge testing — read before running

Purge is the only destructive operation. **Do not run it against
`dumps/enwiki/` or `dumps/simplewiki/`** — findings #2, #3 and #4 are open, and
#4 means purge enrolls *every* file under the source directory for deletion,
not just dump files. Test it only against a throwaway copy.
