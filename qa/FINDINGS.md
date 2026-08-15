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

## 9. FIXED (2026-08-15) — Wikitext template artifacts leak into exported Markdown

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

**What this looked like** was two distinct wikitext-conversion bugs — a
leaked template name (`Italic title`) and mangled infobox field
concatenation (`ublArikaMatrixSoftwareSpike ChunsoftChunsoft`). **What it
actually was, confirmed by reproducing both real articles' wikitext
directly against `WikitextMarkdownNormalizer._convert()`** (fetched from
`simple.wikipedia.org`, 2026-08-15): a single unhandled exception, not two
formatting bugs.

**Root cause**: `_convert()` iterates `wikicode.filter_templates()`
(recursive by default) and calls `wikicode.remove(tpl)` or
`wikicode.replace(tpl, ...)` on each template found — including templates
*nested inside another template's parameter value*, e.g.
`{{Infobox video game|released={{Start date and age|2023|Jan|26}}}}`
(genuinely common in real infoboxes for release dates, credited-role lists
via `{{ubl|...}}`, etc. — both example articles hit this). Handling the
outer infobox first (found first, being outermost) detaches the nested
template from the tree as a side effect. Reaching that now-detached nested
template next in the same loop and calling `wikicode.remove()` on it raises
`ValueError` from mwparserfromhell's `_do_strong_search` (object no longer
in the tree) — confirmed by direct reproduction, full traceback pinned to
`wikitext_md.py:103`. `normalize()`'s broad `except Exception:` around the
whole `_convert()` call silently caught this and substituted a crude
character-stripped dump of the **entire article** (`re.sub(r"[\[\]{}|'#=]",
"", raw_text)` then join non-empty lines) — which is exactly what produces
both symptoms: `{{Italic title}}` becomes bare `Italic title` once its
braces are stripped, and `{{Infobox video game|developer={{ubl|A|B|C}}...}}`
becomes `infobox video gamedeveloperublABC...` once every `{`, `}`, `|`, `=`
is stripped with nothing to replace them. Two visually different symptoms,
one crash, two different articles' template mixes.

**Fixed**: `wikicode.filter_templates()` (and the two `wikicode.filter_tags()`
calls, defensively — HTML `<table>` can nest too) now pass
`wikicode.RECURSE_OTHERS` instead of the default recursive iteration. This
yields only templates/tags not themselves nested inside another one already
in the same pass, so removing/replacing an outer node can no longer orphan
one still queued in the loop; nested templates simply disappear along with
their parent, which is already the desired outcome (the existing
`is_scalar` check already refuses to build a Facts entry from a value
containing `{`, so a nested template inside an infobox param was always
going to make that whole infobox `infobox_skipped` — it just needs to not
crash getting there).

**Verified**: both real articles' wikitext (embedded verbatim as regression
fixtures in `tests/normalization/test_wikitext_md.py`, fetched 2026-08-15)
now normalize cleanly — `infobox_skipped` warning (correct: both infoboxes
have nested-template params), no leaked template names, no stray `{`/`}`,
correct heading/bold/italic conversion, body prose intact. Also added a
synthetic scalar-infobox test asserting the **Facts** bullet-list path
itself (never exercised by the two real examples, since both happen to hit
`infobox_skipped`) — neither real article's infobox has an all-plain-text
`|key=value` set, so this needed its own dedicated case. The prior
`test_normalize_infobox_and_malformed` test asserted
`has_facts or has_skipped or len(doc.markdown) > 0` — true almost
regardless of output — replaced with exact-content assertions. Full engine
suite: 140/140 passing; `ruff check`, `ruff format --check`, `mypy --strict`
all clean.

**Not re-verified against a full real-data rebuild** (the 3,372-article
simplewiki build that originally surfaced this) — that would require
re-downloading and re-running the full pipeline, which wasn't repeated this
pass. The two example articles from the original 75%-failure run are now
confirmed fixed directly; the fix (stop recursing into templates already
covered by an ancestor) is general, not per-article, so it should account
for the class of failure, but the exact prior 75% figure is not re-measured.

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
build`. **Verified**: pushing `v0.1.0-rc2` produced a fully green
`macos-latest` job (real `security import` no longer attempted; the "not
set -- unsigned/ad-hoc-signed" warning fires as designed).

---

## 16. MEDIUM (release pipeline, Linux-specific) — `release.yml`'s Node license SBOM step failed on ubuntu-latest from real disk exhaustion, and hid its own error

**Discovered**: the same `v0.1.0-rc1` run that surfaced #15 also failed
`ubuntu-latest` at "SBOM - Node dependencies (license report)" (`pnpm
-C apps/desktop licenses list --json > apps/desktop/node-dependencies.json`)
— exit code 1, zero stdout and zero stderr visible in the CI log, in under
0.5s. Initially suspected as GitHub-side flakiness (the same run's
annotations show the Actions cache service returning `400` on restore and
failing to save), since a matching pnpm version (9.15.9) with a fresh
install reproduced nothing — neither locally on macOS nor in a clean
`node:20-bookworm` Docker container. **It recurred identically on
`v0.1.0-rc2`** (same step, same instant failure, same silence) after the
#15 fix was confirmed working on the very same run — ruling out flakiness.

**Root cause, confirmed by deliberate reproduction**: by the time this step
used to run, `ubuntu-latest` had already done a full non-debug `pnpm tauri
build` (Rust release compile), a *second* full cargo compile installing
`cargo-cyclonedx`, and a PyInstaller sidecar build — the cumulative disk
footprint fills the runner's limited SSD. `pnpm licenses list` does
bookkeeping writes even for what looks like a read-only report, and once
the disk was full it failed with `ERR_PNPM_MISSING_PACKAGE_INDEX_FILE`.
Reproduced locally by installing the same dependency tree with pnpm 9.15.9
inside a Docker container with its filesystem deliberately filled to <5 KB
free: identical error code, identical near-instant timing, identical *zero
stderr* — because pnpm writes this particular error to **stdout**, and the
step's own `> node-dependencies.json` redirect silently buried it in a file
nothing ever read, in both the real CI runs and the local repro.

**Fixed**: moved the step to run immediately after "Install desktop
dependencies", before any of the Tauri/cargo/PyInstaller builds — it only
ever needed the installed Node dependency tree, not any build artifact, so
there was never a real reason for it to run last. Also changed the command
to `... || { cat apps/desktop/node-dependencies.json; exit 1; }` so a
future failure of this kind prints its own (stdout-only) error into the CI
log instead of silently disappearing into an unread file. **Verified the
reorder and error-surfacing both work as intended** on `v0.1.0-rc3`: the
job now fails in 1m26s (right after "Install desktop dependencies", before
any heavy build) instead of ~10-16 minutes in, and the error is now visible
in the CI log instead of silent — which is what surfaced #17 below.

---

## 17. REFUTED — pnpm store cache corruption was NOT the cause of the ubuntu SBOM failure

**Original hypothesis** (recorded here for an honest trail, not because it
was right): with #16's error now surfaced instead of silently buried,
`v0.1.0-rc3`'s `ubuntu-latest` job still failed the same step, with
`ERR_PNPM_MISSING_PACKAGE_INDEX_FILE` for `@napi-rs/lzma-linux-x64-gnu@1.5.1`
— a different package than #16's `@tauri-apps/cli@2.11.4`, and too fast
(1m26s total) for #16's disk-exhaustion mechanism to apply. All real runs
of this workflow so far showed GitHub's own annotations reporting
Actions-cache-service errors ("Cache service responded with 400" / "Our
services aren't available right now") on this exact job, which looked like
a plausible, well-correlated external cause, so `cache: 'pnpm'` was dropped
from `Setup Node.js` and `v0.1.0-rc4` was pushed to test it.

**Refuted by that very test**: `v0.1.0-rc4` failed with the *exact same*
error, same package, same everything — with the pnpm cache already
removed. Correlation with the cache-service annotation was real but not
causal; the annotation appears on essentially every job in this repo right
now regardless of outcome (a live, unrelated GitHub-side incident), and
chasing it without confirming causation was a mistake worth naming
explicitly. The real cause is #18. The cache removal itself is harmless
and was left in place (a rarely-run workflow doesn't need the cache), but
it did not fix anything.

---

## 18. MEDIUM (release pipeline, Linux-specific) — `pnpm licenses list` fails on optional deps skipped for Node engines mismatch, and `release.yml` pinned an old Node

**Discovered**: after #17 was refuted, reproduced the exact
`v0.1.0-rc3`/`rc4` failure locally and deterministically: `docker run
--platform linux/amd64 node:20-bookworm`, a plain `pnpm install
--frozen-lockfile` against `apps/desktop`'s real lockfile (no CI, no GitHub
cache involved at all), then `pnpm licenses list --json` — same error,
same package, every time. Confirmed on both pnpm 9.15.9 (what `release.yml`
pins) and pnpm 10.34.5 (current), so it isn't a version-specific pnpm
regression either.

**Root cause**: `rollup@4.62.4` (a `vite`/`@vitejs/plugin-react` transitive
dependency) optionally depends on `@napi-rs/lzma-linux-x64-gnu@1.5.1`,
whose own `package.json` declares `engines: { node: '^22.20 || ^24.12 ||
>=25' }`. Under Node 20 (what `release.yml`'s `Setup Node.js` step pinned),
pnpm correctly and *silently* skips installing this optional dependency as
engines-incompatible — normal, expected behavior, no warning printed.
`pnpm licenses list`, however, doesn't account for optional dependencies
legitimately skipped this way: it still expects a content-addressable-store
index file for every package the lockfile mentions, doesn't find one for
this one, and throws `ERR_PNPM_MISSING_PACKAGE_INDEX_FILE` instead of
recognizing the skip as valid. Confirmed the fix by re-running the same
local repro with `node:22-bookworm`: the optional dependency installs
normally and `pnpm licenses list --json` exits 0.

**Fixed**: bumped `release.yml`'s `Setup Node.js` `node-version` from `20`
to `22`. `desktop.yml` (the regular CI workflow) stays on Node 20
unchanged, since it never runs `pnpm licenses list` and isn't affected.
Verified locally (Docker, linux/amd64, Node 22, pnpm 9.15.9: clean install
+ `pnpm licenses list --json` exits 0, report includes the previously-
missing package). Not yet re-verified against a real CI run -- that's
`v0.1.0-rc5`.

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
