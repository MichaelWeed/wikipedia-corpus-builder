# ADR 0005: Canonical Corpus Format Independent of Target Consumers

- **Status:** Accepted
- **Date:** 2026-08-13
- **Deciders:** CorpusSieve Architecture Guild

## Context and Problem Statement

Extracted corpora are consumed by diverse downstream tools, such as vector databases (AnythingLLM, Qdrant), fine-tuning pipelines (Axolotl, Unsloth), and document search engines. Binding the primary extraction output format to any single vendor format creates coupling and forces costly re-extractions when switching tools.

## Decision Drivers

- Vendor-neutral, self-contained, lossless intermediate storage format.
- High compression efficiency and fast sequential streaming access.
- Flexible exporter pipeline for secondary formats (Markdown, JSONL, RAG chunks).

## Decision Outcome

Chosen Option: **Canonical Zstandard JSONL Corpus (`corpus.jsonl.zst`)**.

### Implementation Details

- **Canonical Format:** `corpus.jsonl.zst` containing Zstandard compressed lines matching the `CorpusRecord` Pydantic contract.
- **Self-Contained Attribution:** Each record contains complete document metadata (page ID, revision ID, source URL, dump date, categories, selection path) and raw wikitext content.
- **Export Adapters (`corpussieve.exporters`)**: Secondary format exporters transform canonical records into Markdown trees, JSONL fine-tuning files, or vector ingest packs without re-parsing raw XML dumps.

## Consequences

- **Positive:** Single extraction pass produces a permanent, self-contained archive that can be re-exported endlessly into new formats.
- **Positive:** High space savings via `zstandard` compression.
