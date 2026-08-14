# CorpusSieve — Product Roadmap (ROADMAP)

This roadmap outlines the milestones M0 through M7 for CorpusSieve MVP development.

## Milestones

- **M0: Foundations & Contracts (Phase P0)**
  - Repository scaffold, Pydantic contracts, JSON schemas, synthetic fixture generator, CI workflows, and ADRs.
- **M1: Source Inspection & Metadata Index (Phase P1)**
  - Dump inspection, filename detection, SQL dump parser (`page`, `categorylinks`), SQLite metadata indexing.
- **M2: Deterministic Domain Compiler (Phase P2)**
  - Category graph traversal engine, root resolution, article selection, manifest generation, domain lock export.
- **M3: Local AI Assistance (Phase P3)**
  - Provider integration (Ollama, LM Studio), intent-to-facets assistance, boundary questions, branch review cache.
- **M4: Extraction & Canonical Corpus (Phase P4)**
  - Job state machine, seek-based multistream bz2 extraction, fallback sequential extraction, canonical corpus writer.
- **M5: Normalization & Exports (Phase P5)**
  - Wikitext to Markdown normalizer, JSONL exporter with attribution, AnythingLLM ingestion guide.
- **M6: Desktop Application (Phase P6)**
  - Engine IPC protocol server, Tauri v2 + React wizard desktop UI, job progress and log streaming.
- **M7: Safe Purge & Release Engineering (Phase P7)**
  - Purge preconditions and executor, destructive-safety test suite, v0.1 acceptance build.
