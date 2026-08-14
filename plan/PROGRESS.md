# CorpusSieve — Progress Ledger

Check a chunk only after ALL of its DoD commands pass. Format:
`- [x] P1.3 — 2026-08-20 — <one-line note>`

## P0 Foundations & contracts
- [x] P0.1 — 2026-08-13 — Repo scaffold & Typer CLI structure initialized
- [x] P0.2 — 2026-08-13 — Governance docs, licensing, and spec skeletons added
- [ ] P0.3 Contracts (Pydantic models + JSON Schemas)
- [ ] P0.4 Synthetic fixture generator + golden fixtures
- [ ] P0.5 CI workflows
- [ ] P0.6 ADRs 0001–0006

## P1 Source inspection & metadata index
- [ ] P1.1 Source layer skeleton + filename/dump-type detection
- [ ] P1.2 Source fingerprinting
- [ ] P1.3 SQL dump parser (page, categorylinks)
- [ ] P1.4 Metadata SQLite index build
- [ ] P1.5 Metadata query API
- [ ] P1.6 CLI: `source inspect`, `metadata build`, `metadata search`

## P2 Deterministic domain compiler
- [ ] P2.1 Domain definition load/validate + `domain create`
- [ ] P2.2 Root resolution against local categories
- [ ] P2.3 Category graph traversal engine
- [ ] P2.4 Article selection + manifest generation
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
