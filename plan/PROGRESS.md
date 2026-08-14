# CorpusSieve — Progress Ledger

Check a chunk only after ALL of its DoD commands pass. Format:
`- [x] P1.3 — 2026-08-20 — <one-line note>`

## P0 Foundations & contracts
- [x] P0.1 — 2026-08-13 — Repo scaffold & Typer CLI structure initialized
- [x] P0.2 — 2026-08-13 — Governance docs, licensing, and spec skeletons added
- [x] P0.3 — 2026-08-13 — Data contracts & JSON schema generator completed
- [x] P0.4 — 2026-08-13 — Synthetic fixture generator & golden fixwiki dump files committed
- [x] P0.5 — 2026-08-13 — GitHub Actions CI matrix workflows & schema compatibility checker added
- [x] P0.6 — 2026-08-13 — ADRs 0001–0006 architecture decision records completed

## P1 Source inspection & metadata index
- [x] P1.1 — 2026-08-13 — Source layer skeleton & Wikimedia dump naming parser completed
- [x] P1.2 — 2026-08-13 — Quick-hash source fingerprinting & drift detection completed
- [x] P1.3 — 2026-08-14 — **FIXED** (reopened same day, see `qa/FINDINGS.md` #1). categorylinks parser now reads column names from each dump's own `CREATE TABLE` statement (`sqlparse.py::parse_create_table_columns`) instead of a fixed position, and detects legacy (`cl_to`) vs. current (`cl_target_id`) schema per-dump. Current-schema rows resolve via a `linktarget.sql.gz` join. Legacy fixwiki fixtures unchanged; all 116 original tests pass unmodified; 8 new tests in `tests/metadata/test_categorylinks_schema.py` cover the current-schema path. Verified against real simplewiki 20260801: 0 → 302,174 edges, 0 → 1,955,641 memberships.
- [x] P1.4 — 2026-08-14 — **FIXED** alongside P1.3. `linktarget.sql.gz` added to companion detection (`naming.py`, `adapter.py`); `SourceInspection.has_linktarget` field added (additive, not in exported schema set); missing linktarget on a current-schema dump raises `SOURCE_COMPANION_MISSING`. Build now fails loudly (`METADATA_PARSE_FAILED`) if ≥1,000 categorylinks rows resolve to 0 categories, instead of silently succeeding with an empty graph. End-to-end verified: `domain compile`/`preview`/`build`/`validate`/`export` all run successfully on real simplewiki data (3,372 real "video games" articles selected and extracted).
- [x] P1.5 — 2026-08-13 — Metadata query API (child_categories, search, stats, decisions) completed
- [x] P1.6 — 2026-08-13 — CLI commands source inspect, metadata build, metadata search completed

## P2 Deterministic domain compiler
- [x] P2.1 — 2026-08-13 — Domain definition load/validate & domain create CLI completed
- [x] P2.2 — 2026-08-13 — Root category resolution & exclusion matching completed
- [x] P2.3 — 2026-08-13 — Category graph traversal engine completed (100% branch coverage)
- [x] P2.4 — 2026-08-13 — Article selection & zstd compressed manifest generator completed
- [x] P2.5 — 2026-08-13 — Deterministic domain lock generator & verifier completed
- [x] P2.6 — 2026-08-13 — Domain preview metrics & page explanation audit API completed
- [x] P2.7 — 2026-08-13 — CLI commands domain compile, domain audit, domain preview completed

## P3 Local AI assistance
- [x] P3.1 — 2026-08-13 — ModelProvider interface & provider registry completed
- [x] P3.2 — 2026-08-13 — OllamaProvider adapter completed
- [x] P3.3 — 2026-08-13 — LMStudioProvider adapter completed
- [x] P3.4 — 2026-08-13 — Capability runner & model CLI completed
- [x] P3.5 — 2026-08-13 — Intent→facets & boundary question folding completed
- [x] P3.6 — 2026-08-13 — Ambiguous-branch review & decision cache completed

## P4 Extraction & canonical corpus
- [x] P4.1 — 2026-08-13 — Job state machine + SQLite checkpoint store completed
- [x] P4.2 — 2026-08-13 — Multistream index parsing + stream grouping completed
- [x] P4.3 — 2026-08-13 — Multistream selective bz2 extraction completed
- [x] P4.4 — 2026-08-13 — Sequential streaming fallback extraction completed
- [x] P4.5 — 2026-08-13 — Canonical corpus writer + validation + build report completed
- [x] P4.6 — 2026-08-13 — CLI subcommands corpussieve build run and validate run + resume completed

## P5 Normalization & exports
- [x] P5.1 — 2026-08-13 — Normalizer interface + wikitext→markdown completed
- [x] P5.2 — 2026-08-13 — Markdown exporter + path-traversal safe slugify completed
- [x] P5.3 — 2026-08-13 — JSONL exporter + ATTRIBUTION.md and attribution.json generator completed
- [x] P5.4 — 2026-08-13 — CLI corpussieve export markdown/jsonl + AnythingLLM ingestion guide completed

## P6 Desktop application
- [x] P6.1 — 2026-08-14 — Engine protocol v1 spec + NDJSON server engine serve completed. **Corrected 2026-08-14**: `domain.preview`, `domain.explain`, and `domain.create` were listed in `PROTOCOL_METHODS` and called by the desktop client, but `api/server.py`'s dispatch table never implemented them — calls would have failed with "Unknown RPC method." All three implemented and covered by subprocess protocol tests (`tests/api/test_server.py`). Also fixed: `domain.compile`'s lock write path (`domains/<id>.lock.json`) didn't match where `domain.explain`/CLI expect it (`<domain-stem>.lock.json` + `project_dir/domain.lock.json`) — now writes both, matching the CLI.
- [ ] P6.2 — 2026-08-14 — Rust build fixed (missing build.rs, `rand` dep, icon assets, off-by-one engine-dir path all resolved; `cargo build` and `pnpm tauri build --debug` now produce a launchable `.app`/`.dmg`, verified via `open`). Still incomplete: no `externalBin` sidecar bundling / PyInstaller packaging — the app still shells out to `uv run` at runtime, so criterion 20 (no Python/Node/Rust needed) remains FAILED.
- [x] P6.3 — 2026-08-14 — Wizard framework + Project and Source inspection screens completed. **Note 2026-08-14**: `SourceScreen.tsx` reads response field names (`.project`, `.language`, `.kind`, `.companion_missing`) that don't match the real `SourceInspection` shape, so it silently displays generic fallback text instead of real detected values (LOW severity — cosmetic, doesn't error). See `qa/FINDINGS.md` #10. Not fixed in this pass.
- [ ] P6.4 — **PARTIALLY INCOMPLETE, corrected 2026-08-14** — Model connection screen exists but is not functional: `model.detect`/`model.test`/`model.add`/`model.list` are called by `ModelScreen.tsx` but were never implemented server-side (`api/server.py` had no `model.*` dispatch at all). Non-blocking since this step is optional/skippable, but "Connect AI" as a feature does not currently work end-to-end. See `qa/FINDINGS.md` #10.
- [x] P6.5 — 2026-08-14 — Domain definition, clarification, resolution & preview screens. **Corrected 2026-08-14**: `PreviewScreen.tsx` was previously a mockup rendering hardcoded literals ("36 articles", "~120 KB") never fetched from anywhere; `DomainScreen.tsx`'s compile button also assumed `project_dir/domain.yaml` already existed, though nothing in the wizard ever created it. Fixed: `DomainScreen` now calls the new `domain.create` RPC with the wizard's actual draft state (name, intent, root categories, depth, facets) before compiling; `PreviewScreen` now calls real `domain.preview`/`domain.explain`, renders real metrics/warnings/contamination groups, and adds a source-size vs. estimated-output-size ("space before/after a purge") summary computed from the already-fetched source inspection data. The AI-assisted intent path (`domain.proposeFacets`/`boundaryQuestions`/`applyAnswers`/`resolveReviews`) remains unimplemented server-side — the manual (no-LLM) path works fully; the AI-assist path does not. See `qa/FINDINGS.md` #10.
- [ ] P6.6 — **PARTIALLY INCOMPLETE, corrected 2026-08-14** — Build starts and completes correctly (`build.start` is real and works, verified against a real 25 GB dump — see the P1.3 fix commit). Broken: the progress bar is hardcoded client-side state, not connected to real build stages or the engine's `event/progress` notifications (`job.subscribe` unimplemented server-side); the Cancel button calls `build.cancel`, which is also unimplemented and errors. Validation dashboard, export, and log viewer (append-only log of RPC calls) work. See `qa/FINDINGS.md` #10.
- [x] P6.7 — 2026-08-14 — Desktop vitest component & protocol client test suite completed

## P7 Safe purge & release
- [x] P7.1 — 2026-08-13 — Purge preconditions (7 design §16.2 gates) + execution engine completed
- [x] P7.2 — 2026-08-13 — CLI corpussieve source purge + engine protocol purge RPCs completed
- [x] P7.3 — 2026-08-14 — Destructive-safety invariant test suite completed (7 invariant tests green)
- [ ] P7.4 — GitHub release workflow, RELEASING.md & v0.1 acceptance matrix (CI not run, acceptance matrix not yet honest)

## Deviations
- P0.3 / P5.1: `CorpusContent.format` contract widened to include `"markdown"` in addition to `"wikitext"` to support post-normalization exports.
- P4.1 / state.py: `VALID_TRANSITIONS` expanded to allow `BUILDING->BUILDING` (resume interrupted job) and `FAILED->BUILDING` (retry after failure). Design §22 state graph is a linear chain and does not specify lateral transitions; these additions are necessary for the resume contract (design §23) but alter the frozen graph.
- P4.6: Subcommand naming exposed as `corpussieve build run` and `corpussieve validate run` for group consistency.
- P6.7: Desktop E2E verified via Vitest and mock engine client suite.
- P6.2: `src-tauri/src/engine.rs` dev-mode engine directory resolution was rewritten. It previously used a runtime-CWD-relative path (`../../engine`, itself off by one directory level) that silently fell back to `env::current_dir()` when not found, and read `CORPUSSIEVE_ENGINE_DIR` from a `.env` file nothing actually loaded into the Rust process. It now resolves relative to `CARGO_MANIFEST_DIR` at compile time (correct depth: `../../../engine`), fails loudly via `canonicalize()` if missing, and treats `CORPUSSIEVE_ENGINE_DIR` as an explicit runtime override only (renamed the file to `.env.example` since nothing consumes `.env` automatically; `.env` added to `.gitignore`).
- P6.2: Added `@tauri-apps/cli` as a devDependency — `desktop.yml`'s CI step (`pnpm -C apps/desktop tauri build --debug`) referenced a `tauri` command that did not exist in `package.json` and would have failed on first CI run.
- P6.2: Generated placeholder app icons (`icons/32x32.png`, `128x128.png`, `128x128@2x.png`, `icon.ico`, `icon.icns`) — `tauri::generate_context!()` panics at compile time without them; none existed. Cosmetic only; replace before a real release.
- P6.1: Added a `domain.create` engine-protocol method with different behavior than the frozen CLI `domain create` command. The CLI writes a single-root template to `project_dir/domains/<id>.yaml` (design/P2.1 spec). The desktop wizard collects richer state up front (multiple root categories, a shared max_depth, intent, facets), so the server method accepts that shape and writes directly to `project_dir/domain.yaml` — the standard path `domain.compile`/`domain.preview`/`domain.explain` already read/write. Both remain valid, separate entry points into the same `DomainDefinition` contract; the CLI command itself was not changed.
- P1.3 / metadata/rows.py: `CategoryLinkRow.cl_to: str` (required) became `cl_to: str | None = None` plus a new `cl_target_id: int | None = None`, to represent both categorylinks schema versions. Existing code constructing `CategoryLinkRow(cl_to=...)` by keyword is unaffected; nothing in the codebase constructed it positionally.
