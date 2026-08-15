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
| `BuildScreen.tsx` | `build.cancel`, `build.status` | **FIXED (2026-08-14).** `run_build()` now runs on a background thread (`api/server.py::_start_build_background`) so `serve_stdio()`'s stdin loop stays free to serve `build.cancel`/`build.status` while extraction is in flight; `build.status` polls real `ProgressEvent`s. `job.subscribe` (true server-push notifications) is still not implemented — the Rust sidecar bridge (`engine.rs`) already opportunistically forwards notification lines as `engine-event`, but only while it happens to be blocking on a read for some other call, so it can't be relied on as the primary channel without a dedicated always-reading task; polling was the lower-risk fix. See PROGRESS.md P6.6 and the commit for full detail, including a second bug this surfaced: `metadata.build` never persisted the source dump's location, so `build.start` failed for any project whose source wasn't manually placed at `project_dir/source` — now fixed by writing `project_dir/project.yaml`. |
| *(none currently)* | `project.create`, `project.open`, `project.get` | Not implemented, but also not currently called by any screen — `ProjectScreen.tsx` only sets local wizard state. |

**What does work end-to-end today** (verified by this session's protocol
tests and manual runs): `source.inspect`, `metadata.build`,
`model.detect`/`model.add`/`model.list`/`model.test`,
`domain.create`/`domain.proposeFacets`/`domain.boundaryQuestions`/`domain.applyAnswers`/`domain.compile`/`domain.preview`/`domain.explain`,
`build.start`/`build.status`/`build.cancel`, `corpus.validate`, `export.markdown`/`export.jsonl`,
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

## 11. MEDIUM (test hermeticity) — `test_cli_export_markdown_and_jsonl` never ran hermetically, always failed on a genuinely fresh checkout

**Discovered** the hard way: this test passed on every local run throughout
the entire session (P6.6, P6.2, P7.4 work) but failed on the *very first*
real CI run after pushing to GitHub — on all 3 OS, in `engine.yml`
(2026-08-14). It read `tests/fixtures/fixoutput/corpus`, falling back to
`scratch/fixoutput/corpus` — **neither of which any test in this repo
generates or commits**. It only ever passed because this session's worktree
happened to have a leftover `fixoutput` corpus from an earlier ad-hoc run
(from before this session even started, inherited from the original
worktree). A genuinely fresh checkout — which is all real CI ever is — hit
the fallback path finding nothing there either, and failed with exit code 2.

**Fixed**: `tests/cli/test_export_cli.py` now builds a real corpus from the
committed `fixwiki` fixture inside the test itself (`_build_real_corpus`,
same pattern as `tests/extraction/test_build.py`), making it fully
self-contained. Verified locally (137/137 tests pass, first fully clean run
of this session).

**Also discovered by the same first CI run**, both now fixed:
- `desktop.yml`/`release.yml`'s Linux system-dependency list installed both
  `libappindicator3-dev` and `libayatana-appindicator3-dev`, which
  *conflict* with each other (`apt-get` exit 100: "Unable to correct
  problems, you have held broken packages"). Only the latter (Tauri v2's
  currently documented package) is installed now.
- Neither `desktop.yml`'s bare `cargo check`/`cargo test` steps had ever run
  after a genuinely fresh `pnpm -C apps/desktop build` — this session's own
  local testing always had a leftover `apps/desktop/dist/` from earlier
  manual `pnpm build` runs, so the missing step was invisible locally.
  `tauri::generate_context!()` panics at compile time without `dist/`
  (`frontendDist` config points at it) — real CI hit this on both macOS and
  Windows ("proc macro panicked ... frontendDist ... doesn't exist").
  Reproduced locally by deleting `dist/` and `target/` fresh, confirmed the
  fix (`pnpm -C apps/desktop build` before any bare `cargo` step) resolves
  it.

This did **not** make CI pass end to end — the very next push surfaced two
more, entirely different, previously latent bugs (#12, #13 below). Each
fix so far has been real and locally verified before pushing, but "verified
locally" and "actually green on real CI" have repeatedly turned out to be
different claims for this project; treat any status here as provisional
until a run is actually observed green.

---

## 12. MEDIUM (test hermeticity, Windows-specific) — `test_changed_source_blocks_purge` tampered the wrong file on Windows

**Discovered** on the *second* real CI run (2026-08-14), after fixing
finding #11: `engine.yml` passed on ubuntu/macos's pytest step but failed
on Windows: `test_changed_source_blocks_purge` asserted `plan is None`
(purge should be blocked because the source changed) but got a real
`PurgePlan` back — the precondition check found no change.

**Root cause**: the test picks "a dump file" via
`[f for f in source_dir.iterdir() if f.is_file()][0]` and tampers it.
`tests/fixtures/fixwiki/` also contains `expected.json` (not a Wikimedia
dump file — used by other tests to assert expected traversal output),
which `shutil.copytree` carries into `source_dir` alongside the 5 real dump
files. `expected.json` sorts alphabetically before every `fixwiki-...`
filename. NTFS directory enumeration (what Windows' `iterdir()` walks) is
close to alphabetical; APFS/ext4 are not. So `dump_files[0]` picked
`expected.json` on Windows and one of the real dump files on macOS/Linux —
by luck, not by design. `check_purge_preconditions`'s fingerprint check
(correctly) only scans files `parse_dump_filename` recognizes, so tampering
`expected.json` was invisible to it: the fingerprint genuinely didn't
change, and the assertion that it should have caught a real regression here
never got exercised on Windows at all, for as long as this test has existed.

**Fixed**: filter to `parse_dump_filename(f.name)`-recognized files before
picking one to tamper. Verified locally (7/7 safety tests pass) — the
underlying platform-dependent-iteration-order behavior can't be reproduced
on macOS, so this fix's correctness rests on the root-cause analysis above,
not a local repro; the next Windows CI run is the actual test of it.

---

## 13. LOW (CI fragility) — fixture regeneration isn't byte-identical across platforms

**Discovered** on the same second CI run: `engine.yml`'s "Fixture
Regeneration Diff Check" (`tests/fixtures/generator.py` then
`git diff --exit-code tests/fixtures/fixwiki`) failed on both ubuntu-latest
and macos-latest — regenerating produced **different compressed bytes on
each**, both different from what's committed, for `fixwiki-*-page.sql.gz`
and `fixwiki-*-categorylinks.sql.gz`. `bz2`-compressed fixtures (3 of the 5
files) showed no drift.

**Root cause**: `generator.py` already passes `mtime=0` to `gzip.compress`
for exactly this reason, but that only pins the gzip header's embedded
timestamp — it doesn't make the DEFLATE-compressed *byte stream* identical
across zlib versions. Different platforms ship different zlib versions,
and zlib does not guarantee bit-for-bit identical compressed output across
versions for identical input, even at a fixed compression level. `bz2` has
no equivalent timestamp field and, empirically, no equivalent cross-version
byte drift here either. This was always a latent risk in "commit compressed
binary fixtures, verify regeneration is byte-identical" — it just took
running the check on a machine other than the one that produced the
committed fixtures to surface it, which had never happened before real CI.

**Fixed**: added `engine/scripts/check_fixture_drift.py`, used by both
`qa/run_all_gates.sh` and `engine.yml` in place of a raw `git diff
--exit-code`. It decompresses `.gz` fixtures before comparing (so a
genuine content regression is still caught — verified locally both ways:
a content-identical, byte-different gzip re-encode reports no drift; an
actually-different-content gzip reports drift). Non-gzip fixture files are
still compared byte-for-byte.

---

## 14. LOW (test hermeticity, Windows-specific) — the P6.2 sidecar Rust test's own cleanup could fail on Windows

**Discovered** on the *third* real CI run (2026-08-14), after fixing #12
and #13: ubuntu-latest and macos-latest both went fully green for the first
time. windows-latest failed a different test: `engine.rs`'s
`spawns_bundled_sidecar_and_completes_a_real_rpc_round_trip` (added in the
P6.2 packaging work) panicked with "cleanup must remove the copied
sidecar".

**Root cause**: the test spawns the bundled sidecar binary, kills it, waits
on it, then immediately calls `std::fs::remove_file` on the copy it made.
On Windows, the OS can hold an executable's file locked/mapped for a short
time after the owning process has been killed and `wait()`ed on — the image
teardown finishes asynchronously — so an immediate delete can fail with a
sharing violation right after `wait()` returns. POSIX has no equivalent
lock, which is why this was invisible on macOS/Linux (both passed cleanly).

**Fixed**: retry the removal with a short backoff (up to 20 attempts, 50ms
apart — comfortably more than the lock is ever held) instead of asserting
success on the first try; a persistent failure after all retries is logged,
not a panic, since this is the test's own housekeeping, not the production
round-trip result the test actually exists to verify. Verified locally
(passes on macOS, where the retry loop is a no-op fast path since
`remove_file` just succeeds immediately) — like finding #12, the actual
Windows lock-timing behavior can't be reproduced locally on macOS, so this
fix's correctness rests on the root-cause analysis above until the next
Windows CI run confirms it.

---

## 15. MEDIUM (release pipeline) — `release.yml`'s macOS build always failed codesigning, even with no signing secrets configured

**Discovered** on the *first-ever* real run of `release.yml` (2026-08-14),
triggered by pushing the `v0.1.0-rc1` tag: `windows-latest` went fully
green, but `macos-latest` failed at "Build desktop installers (Tauri)":
`Error failed to bundle project: failed codesign application: failed to run
command security import: failed to import keychain certificate`. No Apple
signing secrets are configured on this repo (`gh secret list` is empty), so
this should have hit the "unsigned/ad-hoc-signed" degraded path the
workflow's own comments and warning step assume exists.

**Root cause**: GitHub's `secrets.*` context evaluates to `""` (empty
string), not unset, for a secret that doesn't exist. The step set
`APPLE_CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}` unconditionally, so
the env var was always *present* in the job, just empty. Tauri v2's
bundler decides whether to codesign based on whether `APPLE_CERTIFICATE`
is set at all, not whether it's non-empty — so it always attempted to
`security import` an empty certificate into the keychain and always failed
the build, regardless of whether real secrets were ever provisioned. This
was invisible until a real tag push actually ran the job; nothing in local
testing (verified only via `tauri build --debug`, per P7.4) exercises this
env-var-presence codepath.

**Fixed**: `Build desktop installers (Tauri)` now runs as a small bash
script (`shell: bash`, so it's identical across all 3 OSes including
Windows, which defaults to pwsh) that `unset`s the Apple/Windows signing
vars when their certificate var is empty, before invoking `pnpm tauri
build`. Not yet re-verified against a real CI run — that's the next step
(a `v0.1.0-rc2` tag).

**Also observed, not treated as a workflow bug**: the same run's
`ubuntu-latest` job failed separately at "SBOM - Node dependencies (license
report)" (`pnpm licenses list --json`) — exit code 1, zero stdout and zero
stderr captured, in under 0.5s. Could not reproduce with a matching pnpm
version (9.15.9) and a fresh `pnpm install`, either locally on macOS or in
a clean `node:20-bookworm` Docker container — both produced the full
license report successfully. The same run's own annotations show GitHub's
Actions cache service returning `400` on restore and failing to save on
this and the Windows job ("Our services aren't available right now"),
consistent with a concurrent GitHub-side infrastructure incident rather
than a deterministic bug in this workflow. Left as-is pending a second real
run; if it recurs on `v0.1.0-rc2` it gets its own numbered finding instead
of being dismissed as flakiness a second time.

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
