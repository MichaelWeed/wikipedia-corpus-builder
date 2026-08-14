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
- [x] P6.2 — 2026-08-14 — Rust build fixed (missing build.rs, `rand` dep, icon assets, off-by-one engine-dir path all resolved; `cargo build` and `pnpm tauri build --debug` now produce a launchable `.app`/`.dmg`, verified via `open`). **Sidecar packaging completed 2026-08-14**: `engine/scripts/build_sidecar.sh` freezes the engine into a standalone PyInstaller executable (`--onefile`, no Python needed to run it — verified with a sanitized `PATH` containing no `uv`/`python`) and places it at `apps/desktop/src-tauri/binaries/corpussieve-engine-<target-triple>`, matching Tauri's `externalBin` naming convention (declared in `tauri.conf.json`'s `bundle.externalBin`). `engine.rs::spawn_sidecar()` now spawns the bundled binary (resolved as `current_exe().parent()/corpussieve-engine[.exe]`, matching where Tauri's bundler actually places it — confirmed empirically by inspecting a real `tauri build --debug` output bundle's `Contents/MacOS/`) when one exists next to the running executable, falling back to the dev-mode `uv run` invocation otherwise (detected by binary presence, not debug/release build flavor, since `tauri build --debug` — what CI runs — still has `debug_assertions` on but does have the sidecar bundled). New Rust test (`engine.rs`) copies the real built sidecar next to the test binary and does a genuine `engine.hello` round trip through `spawn_sidecar()` — not just a presence check. `qa/run_all_gates.sh` and `desktop.yml` CI now build the sidecar (once, cached locally; fresh each run in CI) before the Rust steps, since declaring `externalBin` makes Tauri's build script fail *any* `cargo build` — including `cargo check` — if the binary is missing. **Verified only on macOS** (this session's platform) — Windows/Linux target-triple naming and `.exe` suffix handling follow Tauri's documented convention but could not be exercised here; the CI matrix (`desktop.yml`) will be the first real test on those platforms.
- [x] P6.3 — 2026-08-14 — Wizard framework + Project and Source inspection screens completed. **Note 2026-08-14**: `SourceScreen.tsx` updated to read real `SourceInspection` response fields (`fingerprint.project`, `fingerprint.language`, `dump_kind`, `has_*` booleans, `warnings`).
- [x] P6.4 — 2026-08-14 — Model connection and AI provider selection screen completed. `model.detect`, `model.add`, `model.list`, `model.test` implemented server-side and verified via subprocess protocol test (`tests/api/test_server.py`).
- [x] P6.5 — 2026-08-14 — Domain definition, clarification, resolution & preview screens. `DomainScreen` calls `domain.create` with wizard draft state; `PreviewScreen` calls `domain.preview`/`domain.explain`. AI-assisted intent path (`domain.proposeFacets`, `domain.boundaryQuestions`, `domain.applyAnswers`) implemented server-side and verified via subprocess protocol test (`tests/api/test_server.py`). `domain.resolveReviews` left unimplemented (no engine backend exists).
- [x] P6.6 — 2026-08-14 — **Fixed.** `build.start` was fully synchronous (blocked the stdin-dispatch loop for the whole extraction), so `build.cancel` could never be read until the build was already done, and the progress bar was hardcoded client-side state. `run_build()` now runs on a background thread inside the server process (`api/server.py::_start_build_background`); `build.start` returns as soon as a job_id exists (real setup work only — lock verification/traversal/disk preflight — not the extraction itself); `build.status` polls real `ProgressEvent`s published from `run_build` (stage/completed/total/message) plus terminal succeeded/failed/cancelled state, tracked by a small in-process `jobs/registry.py` and falling back to the persisted `JobStore` row for a job started by a prior process; `build.cancel` sets that job's `cancel_event`, which `run_build` (and, for faster response mid-bz2-group, `extract_multistream`/`extract_sequential`) already checked but nothing ever set in production. `BuildScreen.tsx` now polls `build.status` every 1.5s instead of expecting a synchronous final report. Also fixed in the same pass: `metadata.build` never persisted the source dump's real location, so `build.start` failed with "Source path .../project_dir/source does not exist" for any project whose dump wasn't manually placed at that exact path — the normal case, since `SourceScreen.tsx` lets a user point at a dump anywhere on disk. `metadata.build` now writes `project_dir/project.yaml` with `source_paths`, which `run_build` already read but nothing wrote. Verified live against a real subprocess: `build.cancel` sent immediately after `build.start` genuinely stopped an in-flight extraction with no corpus promoted (`build.status` → `cancelled`); new tests in `tests/extraction/test_build.py` and `tests/api/test_server.py`.
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
- P6.2: `keyring`'s backend discovery (used by `models/config.py::store_auth_token`/`get_auth_token`, for non-loopback provider auth tokens) uses `importlib.metadata` entry points at runtime, which PyInstaller's static import analysis can miss — no dedicated hook exists in `pyinstaller-hooks-contrib` for it. Not verified either way in the frozen sidecar. Low risk: both functions already wrap all calls in `contextlib.suppress(Exception)`/try-except, so a broken backend degrades to "token not stored/retrieved" rather than a crash, and no current RPC method actually calls `store_auth_token` yet (nothing in `server.py`'s dispatch table writes one). Worth a real check before non-loopback provider auth is wired up server-side.
- P6.1: Added a `domain.create` engine-protocol method with different behavior than the frozen CLI `domain create` command. The CLI writes a single-root template to `project_dir/domains/<id>.yaml` (design/P2.1 spec). The desktop wizard collects richer state up front (multiple root categories, a shared max_depth, intent, facets), so the server method accepts that shape and writes directly to `project_dir/domain.yaml` — the standard path `domain.compile`/`domain.preview`/`domain.explain` already read/write. Both remain valid, separate entry points into the same `DomainDefinition` contract; the CLI command itself was not changed.
- P1.3 / metadata/rows.py: `CategoryLinkRow.cl_to: str` (required) became `cl_to: str | None = None` plus a new `cl_target_id: int | None = None`, to represent both categorylinks schema versions. Existing code constructing `CategoryLinkRow(cl_to=...)` by keyword is unaffected; nothing in the codebase constructed it positionally.
