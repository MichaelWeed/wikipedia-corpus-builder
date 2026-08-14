# CorpusSieve — Data Contracts Specification (DATA_CONTRACTS)

All data structures in CorpusSieve are defined as Pydantic v2 models in `engine/src/corpussieve/contracts/` and exported as standard JSON Schemas in `schemas/`.

## Primary Data Contracts

1. **DomainDefinition** (`schemas/domain-definition.schema.json`): User-written specification of domain scope.
2. **DomainLock** (`schemas/domain-lock.schema.json`): Compiled, reproducible resolution map.
3. **ManifestRecord** (`schemas/manifest-record.schema.json`): Stream of pages selected for extraction.
4. **CorpusRecord** (`schemas/corpus-record.schema.json`): Extracted article record in canonical zstandard JSONL corpus.
5. **ProjectFile** (`schemas/project-file.schema.json`): Project configuration and state tracker.
6. **BuildReport** (`schemas/build-report.schema.json`): Summary statistics and validation metrics of a corpus build.

## Hashing Rules

- `quick_hash`: SHA-256 over `first 64 KiB ∥ last 64 KiB ∥ size_bytes (8-byte big-endian)`.
- `canonical_json_hash`: SHA-256 over UTF-8 encoded canonical JSON (`sort_keys=True`, separators `(",", ":")`).
