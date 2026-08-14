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
- [ ] P2.5 Domain lock generation (deterministic path)
- [ ] P2.6 Preview & audit
- [ ] P2.7 CLI: `domain compile`, `domain audit`, `domain preview`

## P3 Local AI assistance
- [ ] P3.1 ModelProvider interface + provider registry
- [ ] P3.2 OllamaProvider
- [ ] P3.3 LMStudioProvider
- [ ] P3.4 Capability test + `model detect` / `model test` CLI
- [ ] P3.5 Intent→facets + boundary questions
- [ ] P3.6 Ambiguous-branch review + decision cache

## P4 Extraction & canonical corpus
- [ ] P4.1 Job state machine + checkpoint store
- [ ] P4.2 Multistream index parsing + stream grouping
- [ ] P4.3 Multistream selective extraction
- [ ] P4.4 Sequential fallback extraction
- [ ] P4.5 Canonical corpus writer + validation + build report
- [ ] P4.6 CLI: `build`, `validate` + resume

## P5 Normalization & exports
- [ ] P5.1 Normalizer interface + wikitext→markdown
- [ ] P5.2 Markdown exporter
- [ ] P5.3 JSONL exporter + attribution
- [ ] P5.4 CLI: `export` + AnythingLLM ingestion guide

## P6 Desktop application
- [ ] P6.1 Engine protocol v1 (spec + Python server)
- [ ] P6.2 Tauri scaffold + sidecar wiring
- [ ] P6.3 Wizard: project + source screens
- [ ] P6.4 Wizard: model connect screens
- [ ] P6.5 Wizard: domain define/clarify/resolve/preview screens
- [ ] P6.6 Build/validate/export screens + progress + log viewer
- [ ] P6.7 Desktop E2E tests (mocked engine)

## P7 Safe purge & release
- [ ] P7.1 Purge preconditions + executor
- [ ] P7.2 Purge UX (CLI + desktop confirmations)
- [ ] P7.3 Destructive-safety test suite
- [ ] P7.4 Release engineering + v0.1 acceptance run

## Deviations
(record any spec deviation here: chunk ID, what changed, why, smallest workaround)
