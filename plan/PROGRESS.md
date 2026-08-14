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
- [x] P1.3 — 2026-08-13 — Streaming SQL parser (page, categorylinks) & title normalization completed
- [x] P1.4 — 2026-08-13 — Atomic SQLite metadata index builder completed
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
- [x] P6.1 — 2026-08-13 — Engine protocol v1 spec + NDJSON server engine serve completed
- [ ] P6.2 — Tauri v2 + React 18 desktop scaffold + typed EngineClient (sidecar packaging incomplete)
- [x] P6.3 — 2026-08-14 — Wizard framework + Project and Source inspection screens completed
- [x] P6.4 — 2026-08-14 — Model connection and AI provider selection screen completed
- [x] P6.5 — 2026-08-14 — Domain definition, clarification, resolution & preview screens completed
- [x] P6.6 — 2026-08-14 — Build progress, validation dashboard, export & log viewer screens completed
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
