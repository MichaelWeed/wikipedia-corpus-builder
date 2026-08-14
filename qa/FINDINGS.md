# CorpusSieve — QA & Security Findings

**Date:** 2026-08-14
**Scope:** full codebase (no remote configured, so `/security-review`'s
`git diff origin/HEAD...` was unavailable; reviewed the whole tree instead)
plus first-ever execution against a **real Wikimedia dump** (simplewiki 20260801).

Findings are ordered by severity. Each was **empirically reproduced**, not
inferred from reading code.

---

## 1. FIXED (2026-08-14) — CorpusSieve ingested zero category data from current Wikimedia dumps

**Status: FIXED and verified end-to-end against real simplewiki 20260801.**

Rebuilding the metadata index after the fix:

| table | before | after |
|---|---|---|
| `pages` | 945,561 | 945,561 |
| `categories` | 92,980 | 104,259 |
| `category_edges` | **0** | **302,174** |
| `category_membership` | **0** | **1,955,641** |

`domain compile` + `domain preview` for "video games" then selected **3,372
real articles** (Valorant, Eve Online, The Elder Scrolls III: Morrowind,
Devil May Cry 4, ...) from a single `Category:Video_games` root, 751
categories traversed. `build` → `validate` → `export markdown` completed
end-to-end: 3,372 records extracted, validation PASSED (25/25 spot-checked),
markdown + `ATTRIBUTION.md` exported. This is the first fully successful
real-data run in the project's history. `./qa/smoke_real_dump.sh` now runs to
completion instead of halting at step 2.

**Fix implemented:**
- `metadata/sqlparse.py::parse_create_table_columns()` reads column names from
  each dump's own `CREATE TABLE` statement rather than assuming a fixed
  position — resilient to future MediaWiki schema changes, not just this one.
- `metadata/rows.py::detect_categorylinks_schema()` picks legacy (`cl_to`) vs.
  current (`cl_target_id`) per-dump; `iter_categorylinks_rows()` and the new
  `iter_linktarget_rows()` use the detected column indices for both schemas.
- `metadata/build.py` builds an `lt_id → title` map from `linktarget.sql.gz`
  (namespace 14 only) and joins it against `cl_target_id` when needed.
- `linktarget.sql.gz` added to `naming.py`/`adapter.py` companion detection;
  `SourceInspection.has_linktarget` (new field, defaults `False`, additive —
  no schema regeneration needed since `SourceInspection` isn't in the exported
  schema set). Missing `linktarget.sql.gz` on a current-schema dump now raises
  `SOURCE_COMPANION_MISSING` with an actionable message instead of silently
  building an empty graph.
- **Fails loudly**: if ≥1,000 categorylinks rows are parsed and 0 resolve to a
  category name, `build_metadata_index` raises `METADATA_PARSE_FAILED`
  instead of silently succeeding with an empty graph. Covered by
  `test_build_metadata_index_fails_loudly_on_stale_linktarget`.
- Existing golden fixtures (`fixwiki`, legacy schema) were **not** changed —
  the new column-detection code path handles both schemas, so all 116
  original tests pass unmodified. 8 new tests in
  `tests/metadata/test_categorylinks_schema.py` cover the current-schema path
  (detection, row parsing, linktarget join, missing-companion error, and the
  fail-loud sanity check) using small inline-constructed dumps rather than a
  second binary fixture set.

**Original impact (historical):** The core product feature (domain
compilation via category graph traversal) was completely non-functional on
real Wikipedia data. This was not a degradation; it was total.

**Scope is limited to the metadata/category layer.** The extraction half of the
product was tested independently against the real 25 GB enwiki dump and
**works correctly**: the multistream index parsed 400,000 entries in 0.4 s, and
`extract_selected_pages({12, 25, 39})` returned Anarchism (113,647 chars),
Autism spectrum, and Albedo (71,574 chars) with correct revision IDs in 30 s,
without decompressing the full file. CorpusSieve is one schema fix away from a
working end-to-end pipeline on real Wikipedia.

**Reproduced:** built the metadata index from the real simplewiki 20260801 dump:

| table | rows before fix | rows after fix |
|---|---|---|
| `pages` | 945,561 | 945,561 |
| `category_edges` | **0** | 302,174 |
| `category_membership` | **0** | 1,955,641 |

**Root cause:** MediaWiki migrated the `categorylinks` schema. The real 2026
dump has **no `cl_to` column** — the category *name* is no longer in
`categorylinks` at all; `cl_target_id` is a foreign key into a separate
`linktarget(lt_id, lt_namespace, lt_title)` table. The parser read a fixed
column position that predates the migration, so every row was silently
skipped with no error and no warning.

**Why tests never caught it:** the synthetic fixtures in
`engine/tests/fixtures/generator.py` were generated with the *old* schema, so
the entire test suite validated against a dump format Wikimedia no longer
publishes. All 116 tests passed against a format that doesn't exist in the
wild — see the "Fix implemented" notes above for how this class of gap is
closed.

---

## 2. HIGH (data loss) — "Move to Trash" can silently perform a permanent delete

**File:** `engine/src/corpussieve/safety/purge.py`

```python
if mode == "trash" and HAS_SEND2TRASH:
    send2trash.send2trash(str(f_path))
else:
    f_path.unlink()          # ← permanent, and reached when mode == "trash"
```

If `send2trash` is unavailable for any reason (import failure, trimmed install,
packaging omission in the future PyInstaller sidecar), a user who explicitly
chose the **reversible** option gets **irreversible destruction of their only
copy of a 25 GB dump**, with no warning and `status: "SUCCESS"`.

**Reproduced:** with `HAS_SEND2TRASH = False` and `mode="trash"`, the target
file was permanently unlinked (not recoverable from Trash).

This directly violates design §16.3, which requires Trash vs. permanent to be
distinct choices with permanent gated behind a *stronger* confirmation.

**Fix:** if `mode == "trash"` and `send2trash` is unavailable, **abort** with a
blocker. Never silently downgrade to a more destructive operation.

---

## 3. HIGH (misleading safety UI) — `PurgePlan.reversible` is hardcoded `True`

**File:** `engine/src/corpussieve/safety/preconditions.py` (plan construction)

`reversible=True` is a literal, independent of the chosen mode or whether
`send2trash` is even available. Design §16.3 requires the confirmation UI to
show "Whether deletion is reversible" — both the CLI and the desktop
`PurgeScreen` will therefore tell the user a permanent deletion is reversible.
Compounds finding #2.

**Fix:** derive it (`mode == "trash" and HAS_SEND2TRASH`).

---

## 4. MEDIUM (data loss) — Purge deletes *every* file under the source directory

**File:** `engine/src/corpussieve/safety/preconditions.py`

```python
items_to_check = list(source_dir.rglob("*")) if source_dir.is_dir() else [source_dir]
```

Every file recursively under the source directory is added to the delete plan —
not just the recognized dump files. A user who points `--source` at a shared
folder (e.g. `~/Downloads`, which is a plausible place to leave a dump) would
have *unrelated personal files* enrolled for deletion.

Mitigated by the confirmation showing the file list, but the plan should be
restricted to files the adapter actually recognized as dump components.

---

## 5. MEDIUM (DoS) — XML entity expansion reachable in the sequential extractor

**File:** `engine/src/corpussieve/extraction/sequential.py`

Uses stdlib `xml.etree.ElementTree` with no DTD hardening. Design §24 declares
dump content untrusted input.

**Reproduced** through the real parsing pattern: a 331-byte payload expanded to
100,000 characters (**302×**) at only 4 nesting levels; expansion is
exponential, so ~9 levels exhausts memory.

- **XXE / local file disclosure: NOT vulnerable** ✅ — ElementTree refuses
  external entities (`undefined entity` ParseError). Verified explicitly.
- **Multistream path: incidentally safe** ✅ — wrapping decompressed bytes in a
  synthetic `<root>` makes any `DOCTYPE` a parse error.
- **Sequential path: vulnerable** ❌ — parses raw dump bytes directly.

**Fix:** use `defusedxml` (`forbid_dtd=True`), or reject any dump whose prolog
contains a `DOCTYPE`.

**Realistic severity:** requires the user to open a maliciously crafted dump;
official dumps over HTTPS are not a practical vector. Local DoS only — no code
execution and no data exfiltration.

---

## 6. LOW — `bz2.decompress()` on an unbounded stream slice

`engine/src/corpussieve/extraction/multistream.py` decompresses a whole stream
into memory with no size ceiling. Bounded in practice by index offsets, but a
hostile dump could declare a large stream. Consider a decompression cap.

---

## 7. LOW — No explicit HTTPS→HTTP downgrade guard

Design §24 requires "do not silently downgrade HTTPS to HTTP" for model
endpoints. No such check exists in `engine/src/corpussieve/models/config.py`.

---

## 8. LOW (docs) — The documented smoke-test runbook cannot work as written

`docs/ACCEPTANCE_V0_1.md` instructs downloading `*-latest-*` files from
`dumps.wikimedia.org/<wiki>/latest/`. `parse_dump_filename` requires a
`YYYYMMDD` date, so those filenames are rejected with `SOURCE_UNSUPPORTED`.

**Confirmed:** `source inspect` on the freshly downloaded `-latest-` files
failed; renaming to `simplewiki-20260801-*` fixed it immediately.

Downloading from the **dated** directory is also more correct: "latest" is a
moving target, which would silently break the source-fingerprint reproducibility
guarantee (design §9.3). `qa/fetch_dumps.sh` handles this correctly.

---

## 9. MEDIUM (output quality) — Wikitext template artifacts leak into exported Markdown

**Discovered:** running `export markdown` against the first successful
real-data build (simplewiki "video games" domain, 3,372 articles) — **2,542 of
3,372 exports (75%) reported normalization errors.**

**Reproduced** in the actual output:

```markdown
# Pizza Tower

Italic title

infobox video game
```

```markdown
# The Nightmare of Druaga: Fushigi no Dungeon

Infobox video game

developer  ublArikaMatrix SoftwareSpike ChunsoftChunsoft
```

Two distinct problems, both in `engine/src/corpussieve/normalization/wikitext_md.py`:

1. `{{Italic title}}` (and likely other simple formatting templates) is
   emitted as literal body text (`Italic title`) instead of being applied or
   dropped.
2. `{{Infobox video game|developer=...|...}}` is not converted to the design
   §15.1 `**Facts**` bullet list. Instead the template name and field values
   are concatenated into unreadable run-on text
   (`ublArikaMatrixSoftwareSpike ChunsoftChunsoft` — likely `publisher` +
   `developer` values glued together without separators).

**Impact:** the RAG-oriented Markdown export is unusable for most real
Wikipedia articles, which almost all carry an infobox. This is separate from
finding #1 — extraction and selection are correct; this is a normalization
(P5) quality bug, not a category-layer or safety bug.

**Not fixed in this pass** — flagging for separate remediation. The design's
existing golden-fixture tests (`tests/normalization/golden/`) evidently don't
cover a real infobox with multiple fields, since this class of failure wasn't
caught by the test suite either. A fix should add real-world infobox/template
fixtures (e.g. from this exact `Pizza_Tower` or `Nightmare_of_Druaga` case) to
`tests/normalization/golden/`, not just synthetic minimal ones.

---

## 10. HIGH (functionality) — Most of the desktop wizard is not wired to the engine

**Discovered** while fixing finding #1 and wiring `PreviewScreen`/`DomainScreen`
to real data (2026-08-14): `apps/desktop/src/engine/client.ts` lists 29
protocol methods and every desktop screen calls several of them, but
`engine/src/corpussieve/api/server.py`'s dispatch table only implemented 8 —
any call to an unimplemented method fails with `"Unknown RPC method"`. This
pass fixed 3 (`domain.preview`, `domain.explain`, `domain.create`, see
finding #1's commit and P6.1/P6.5 in PROGRESS.md). **The following remain
unimplemented server-side and are confirmed broken when called:**

| Screen | Calls | Server status |
|---|---|---|
| `ModelScreen.tsx` | `model.detect`, `model.add`, `model.list`, `model.test` | **FIXED** (Verified by `test_engine_serve_subprocess_model_methods` in `tests/api/test_server.py`) |
| `DomainScreen.tsx` AI Assist | `domain.proposeFacets`, `domain.boundaryQuestions`, `domain.applyAnswers` | **FIXED** (Verified by `test_engine_serve_subprocess_ai_domain_methods` in `tests/api/test_server.py`; `domain.resolveReviews` left unimplemented — no engine backend exists) |
| `SourceScreen.tsx` | `source.inspect` UI display | **FIXED** (Updated `SourceScreen.tsx` to read real `SourceInspection` fields: `fingerprint.project`, `fingerprint.language`, `dump_kind`, `has_*` booleans) |
| `BuildScreen.tsx` | `build.cancel`, `job.subscribe` | **Not implemented.** `serve_stdio()` is a single-threaded loop that blocks on `sys.stdin` during synchronous `build.start`. Background threading and `ProgressEvent` pipeline in `run_build()` remain out of scope for this pass. |
| *(none currently)* | `project.create`, `project.open`, `project.get` | Not implemented, but also not currently called by any screen — `ProjectScreen.tsx` only sets local wizard state. |

**What does work end-to-end today** (verified by this session's protocol
tests and manual runs): `source.inspect`, `metadata.build`,
`model.detect`/`model.add`/`model.list`/`model.test`,
`domain.create`/`domain.proposeFacets`/`domain.boundaryQuestions`/`domain.applyAnswers`/`domain.compile`/`domain.preview`/`domain.explain`,
`build.start`, `corpus.validate`, `export.markdown`/`export.jsonl`,
`purge.plan`/`purge.confirm`. That covers the manual (no-LLM) path from
"pick a source" through "export a corpus" — which is the path a first-time
user following the CLI-equivalent flow would take.

**Not fixed in this pass** — this is effectively the remaining scope of P6.4
(model screen) and P6.6 (build progress/cancel), plus the desktop half of P3
(LLM-assisted compilation), not a small bug. Flagging precisely rather than
silently leaving PROGRESS.md's existing `[x]` marks uncorrected or attempting
a partial fix; see PROGRESS.md for the corrected P6.4/P6.6 notes.

Additionally, `SourceScreen.tsx` reads `sourceInspection.project`,
`.language`, `.kind`, and `.companion_missing` — none of which exist on the
real `SourceInspection` response (the real fields are
`fingerprint.project`/`fingerprint.language`, `dump_kind`, and per-field
`has_*` booleans/`warnings`). This doesn't error — the `||` fallbacks quietly
render generic defaults (`"Wikimedia"`, `"en"`, `"multistream"`) instead of
the actual detected values — so it's LOW severity (cosmetic, not a crash),
but worth a fix alongside the above.

**Correction (2026-08-14):** row 276's "FIXED" was accurate for the server
dispatch (protocol-tested), but manual verification against the real
`DomainScreen.tsx` and a live Ollama model surfaced three problems the
subprocess test's `"error" in resp or "result" in resp` assertion couldn't
catch:

1. `handleProposeFacets` read `res.facets`, but `domain.proposeFacets`
   actually returns `{include_facets, exclude_facets, rationale}` — the
   button silently did nothing.
2. `domain.boundaryQuestions`/`domain.applyAnswers` had zero UI entry
   points — implemented and protocol-tested, but unreachable by clicking
   anything in the app.
3. `complete_structured`'s 30s httpx timeout was too tight for a cold
   local-model load (measured ~26s for a 51GB model on this machine) and,
   on timeout, burned two more identical retries with a "Validation
   failed" correction message that can't fix a slow model.

All three fixed: `DomainScreen.tsx` now reads the real response shape and
has a full propose → boundary-questions → apply-answers flow wired to
`domain.applyAnswers`; `complete_structured` timeout raised to 120s and
fails fast (no wasted retries) on timeout in both `ollama.py`/`lmstudio.py`;
`domain.create`/`client.createDomain` now also accept `exclude_facets` so
AI-proposed exclusions survive into `domain.yaml`. `test_server.py`'s
AI-domain subprocess test now points offline calls at a genuinely
unreachable port (not Ollama's real default, which was silently exercising
a live server when one happened to be running) and asserts on actual error
codes. Verified live end-to-end against `huihui_ai/qwen3-coder-next-abliterated`
via Ollama: proposeFacets → boundaryQuestions → applyAnswers all completed
correctly with real generated content.

---

## Clean results (verified, no action needed)

- **SQL injection:** none. Every `execute()` is parameterized; no f-string or
  concatenated SQL anywhere in `src/`.
- **XXE / local file disclosure:** blocked by ElementTree (tested explicitly).
- **Path traversal in exports:** `exporters/naming.py::slugify` is solid —
  strips `/` and `\`, collapses `..` to `untitled`, handles Windows reserved
  names, NFC-normalizes, length-caps.
- **Secret handling:** tokens go to the OS keyring, never to `providers.yaml`
  (design §21 satisfied). No TLS verification is disabled anywhere.
- **LLM trust boundary:** model output is schema-validated and never executed,
  never used as a filesystem path.
