# Project Agent Instructions

Read and follow `plan/00_OVERVIEW.md` as the shared operating policy and master execution plan.

For implementation tasks, `.agent-test-contract.yaml` defines required verification. Do not claim completion until its applicable gates pass with observed exit status 0.

---

## Anti-Drift Rules (Binding)

- **Names are frozen**: Use the Naming Registry exactly. Do not rename packages, modules, CLI commands, schema files, error codes, or job states.
- **Contracts are frozen after P0.3**: Pydantic models in `engine/src/corpussieve/contracts/` and exported JSON Schemas in `schemas/` may only gain fields via a later chunk that explicitly specifies it.
- **No extra dependencies**: Only libraries pinned in `plan/00_OVERVIEW.md` §5 (plus transitive deps). Adding any other runtime dependency is a deviation.
- **No feature invention**: Features in Post-MVP or Non-Goals lists must not be implemented.
- **LLM trust boundary is absolute**: Model output is untrusted data. It is schema-validated, never executed, never used as a filesystem path, and never bypasses human approval gates.
- **Source dumps are read-only**: Everywhere except `safety/purge.py` (P7.1), which is the only module authorized to delete or move source files.

---

## Naming Registry (Frozen)

| Thing | Name |
|---|---|
| Product | CorpusSieve |
| Python package / import / CLI binary | `corpussieve` |
| CLI command groups | `project`, `source`, `metadata`, `model`, `domain`, `build`, `validate`, `export` |
| Project file | `project.yaml` |
| Domain definition | `domain.yaml` (schema `domain-definition.schema.json`) |
| Domain lock | `domain.lock.json` (schema `domain-lock.schema.json`) |
| Manifest | `manifest.jsonl.zst` (record schema `manifest-record.schema.json`) |
| Canonical corpus | `corpus.jsonl.zst` (record schema `corpus-record.schema.json`) |
| Build report | `build-report.json` (schema `build-report.schema.json`) |
| Metadata DB | `cache/metadata.sqlite` |
| Job/state DB | `state.sqlite` |
| Engine IPC protocol | "engine protocol v1" (`engine-protocol.schema.json`) |
| Provider adapters | `OllamaProvider`, `LMStudioProvider` |
| Source adapter | `WikimediaXmlDumpAdapter` |
| Error codes | Exactly 16 error codes in `corpussieve.contracts.errors.ErrorCode` |

---

## Global Verification Commands (DoD)

Before declaring any chunk complete, execute and observe exit status 0 for:

```bash
cd engine && uv run ruff check . && uv run ruff format --check .
cd engine && uv run mypy src
cd engine && uv run pytest -q
```
