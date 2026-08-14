# CorpusSieve — MVP Functional Requirements Spec (MVP_SPEC)

This document details the functional requirements (FR-001 through FR-030) for the CorpusSieve MVP, derived from [SOLUTION_DESIGN.md](file:///Users/johndoe/Projects/corpus_sieve/docs/SOLUTION_DESIGN.md).

## Requirements Matrix

| ID | Feature / System Area | Requirement Summary | Phase / Chunk |
|---|---|---|---|
| FR-001 | Source Inspection | Detect MediaWiki XML dump type (multistream vs sequential) and filename convention | P1.1 |
| FR-002 | Source Fingerprinting | Calculate quick_hash and canonical JSON fingerprint for source dump files | P1.2 |
| FR-003 | SQL Ingestion | Parse MediaWiki `page.sql.gz` and `categorylinks.sql.gz` dumps | P1.3 |
| FR-004 | Metadata Indexing | Build local SQLite index (`cache/metadata.sqlite`) mapping pages and categories | P1.4 |
| FR-005 | Metadata Query | Search metadata index by title, category membership, and namespace | P1.5 |
| FR-006 | Source Inspection CLI | Provide `source inspect`, `metadata build`, and `metadata search` CLI commands | P1.6 |
| FR-007 | Domain Definition | Load, validate, and persist YAML domain definitions (`domain.yaml`) | P2.1 |
| FR-008 | Category Root Resolution | Resolve domain category queries against indexed local categories | P2.2 |
| FR-009 | Traversal Engine | Traversed category graph deterministically up to specified max depth | P2.3 |
| FR-010 | Article Selection | Select articles belonging to included categories and generate manifest | P2.4 |
| FR-011 | Domain Lock | Export deterministic, hash-verifiable `domain.lock.json` | P2.5 |
| FR-012 | Domain Preview & Audit | Generate preview metrics and category decision audit logs | P2.6 |
| FR-013 | Domain Compiler CLI | Provide `domain compile`, `domain audit`, and `domain preview` CLI commands | P2.7 |
| FR-014 | Provider Interface | Abstract local LLM inference via `ModelProvider` registry | P3.1 |
| FR-015 | Ollama Adapter | Support Ollama local AI endpoint discovery and inference | P3.2 |
| FR-016 | LM Studio Adapter | Support LM Studio local AI endpoint discovery and inference | P3.3 |
| FR-017 | Capability Testing | Validate JSON structured output capabilities of local models | P3.4 |
| FR-018 | LLM Intent Assistance | Generate domain facets and boundary questions from user intent | P3.5 |
| FR-019 | Branch Review | Request LLM recommendation for ambiguous graph branches with decision cache | P3.6 |
| FR-020 | Job State Machine | Track extraction job states and maintain checkpoint DB (`state.sqlite`) | P4.1 |
| FR-021 | Multistream Grouping | Group pages by stream offset for efficient seek-based decompression | P4.2 |
| FR-022 | Multistream Extraction | Extract requested articles selectively from bz2 multistream XML dumps | P4.3 |
| FR-023 | Sequential Fallback | Extract articles via single-pass streaming parser for sequential dumps | P4.4 |
| FR-024 | Canonical Corpus Writer | Write `corpus.jsonl.zst` zstandard compressed records and build report | P4.5 |
| FR-025 | Build & Validate CLI | Provide `build` and `validate` CLI commands with job resume capability | P4.6 |
| FR-026 | Normalizer Interface | Convert raw wikitext to clean Markdown using `mwparserfromhell` | P5.1 |
| FR-027 | Markdown Exporter | Export canonical corpus records to structured Markdown files | P5.2 |
| FR-028 | JSONL Exporter | Export canonical corpus records to JSONL with full attribution | P5.3 |
| FR-029 | Export CLI & Integration | Provide `export` CLI command and AnythingLLM ingestion guide | P5.4 |
| FR-030 | Safe Purge | Execute verified source dump purges (`safety/purge.py`) with user confirmation | P7.1 |
