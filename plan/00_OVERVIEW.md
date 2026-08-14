# CorpusSieve — Execution Work Plan (Overview)

**Plan version:** 1.0 (2026-08-13)
**Source of truth for product scope:** `../CorpusSieve_Solution_Design.md` (moves to `docs/SOLUTION_DESIGN.md` in chunk P0.1)
**Source of truth for execution:** this `plan/` directory.

This plan decomposes the CorpusSieve MVP (design milestones M0–M7) into 8 phases
(P0–P7) and 46 chunks. Each chunk is a self-contained unit of work with explicit
deliverable file paths, a specification, an out-of-scope list, and a verifiable
Definition of Done (DoD).

---

## 1. How the executing agent must use this plan

1. Execute chunks **strictly in dependency order**. Within a phase, chunks are
   ordered; do not start a chunk until every chunk in its `Depends:` line has a
   checked DoD in `PROGRESS.md`.
2. Before starting a chunk, read: this overview, the chunk's phase file, and any
   contract files the chunk references. Do **not** re-read the entire solution
   design each time; the plan already encodes it. If the plan and the design doc
   conflict, **the plan wins** — the plan resolves ambiguities the design left open.
3. After finishing a chunk, run every command in its DoD block. All must pass.
   Then check the chunk off in `PROGRESS.md` with the date. Never check off a
   chunk with failing or skipped DoD commands.
4. **Never** widen scope. If a chunk's spec seems to require something not
   listed in its deliverables, implement the minimum inside the listed files. If
   something is genuinely impossible as specified, record the deviation in
   `PROGRESS.md` under "Deviations" with a one-paragraph justification, choose
   the smallest workaround, and continue. Do not silently redesign.
5. No placeholder code. Every function shipped in a chunk is implemented and
   tested per that chunk's spec. `NotImplementedError` is permitted only for
   post-MVP adapter stubs explicitly listed as stubs.
6. Commit per chunk: one commit (or small series) per chunk, message prefixed
   with the chunk ID, e.g. `P1.3: categorylinks SQL ingestion`.

## 2. Anti-drift rules (binding)

- **Names are frozen.** Use the Naming Registry (§4) exactly. Do not rename
  packages, modules, CLI commands, schema files, error codes, or job states.
- **Contracts are frozen after P0.3.** Pydantic models in
  `engine/src/corpussieve/contracts/` and exported JSON Schemas in `schemas/`
  may only gain fields via a later chunk that explicitly says so. Any other
  change is a deviation and must be logged.
- **No extra dependencies.** Only the libraries pinned in §5 (plus their
  transitive deps). Adding any other runtime dependency is a deviation.
- **No feature invention.** Anything in the design's "Post-MVP" or "Non-Goals"
  lists (design §4/§5) must not be implemented, even partially, except the
  explicitly listed interface stubs.
- **LLM trust boundary (design §8.6) is absolute**: model output is data. It is
  schema-validated, never executed, never used as a filesystem path, and never
  bypasses human approval gates.
- **Source dumps are read-only** everywhere except `safety/purge.py` (P7.1),
  which is the only module in the codebase allowed to delete or move source files.

## 3. Repository layout (frozen)

Built in the current directory (`corpus_sieve/`), which becomes the repo root:

```text
.
├── README.md  LICENSE  NOTICE  CONTRIBUTING.md  SECURITY.md
├── CODE_OF_CONDUCT.md  AGENTS.md
├── plan/                      # this plan (kept in-repo)
├── apps/desktop/              # Tauri v2 app: src/ (React) + src-tauri/ (Rust)
├── engine/
│   ├── pyproject.toml
│   ├── src/corpussieve/
│   │   ├── cli/               # Typer command groups
│   │   ├── api/               # engine sidecar protocol server (P6)
│   │   ├── contracts/         # Pydantic v2 models (single source of contracts)
│   │   ├── sources/           # SourceAdapter + WikimediaXmlDumpAdapter
│   │   ├── metadata/          # SQLite metadata index build + queries
│   │   ├── domain/            # compiler, traversal, lock, preview
│   │   ├── models/            # ModelProvider + Ollama/LM Studio adapters
│   │   ├── extraction/        # multistream/sequential extraction, jobs
│   │   ├── normalization/     # Normalizer interface + wikitext→markdown
│   │   ├── validation/        # build validation
│   │   ├── exporters/         # jsonl, markdown, attribution
│   │   ├── safety/            # purge preconditions + purge executor
│   │   └── jobs/              # job state machine, checkpoints, events
│   └── tests/                 # mirrors src layout; fixtures/ inside
├── schemas/                   # exported JSON Schemas (generated, committed)
├── examples/domains/
├── docs/                      # SOLUTION_DESIGN.md, specs, adr/
└── .github/workflows/  ISSUE_TEMPLATE/  PULL_REQUEST_TEMPLATE.md
```

## 4. Naming Registry (frozen)

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
| Error codes | exactly the 16 codes in design §29, as `corpussieve.contracts.errors.ErrorCode` |
| Job states | exactly design §22: `NEW, SOURCE_INSPECTED, METADATA_INDEXING, METADATA_READY, DOMAIN_DRAFT, DOMAIN_COMPILED, PREVIEWED, BUILDING, BUILD_SUCCEEDED, VALIDATING, VALIDATED, EXPORTED, SOURCE_PURGED` plus terminal `FAILED`, `CANCELLED` |
| Selection modes | `high_recall`, `balanced`, `high_precision` |

## 5. Pinned technology decisions (frozen — resolves design's open choices)

**Engine (Python):**
- Python **3.12** (CI floor and target). Package manager: **uv**. Build backend: **hatchling**.
- Runtime deps: `pydantic>=2.7`, `typer>=0.12`, `rich>=13`, `httpx>=0.27`,
  `pyyaml>=6`, `zstandard>=0.22`, `mwparserfromhell>=0.6` (P5 only),
  `platformdirs>=4`, `keyring>=25` (token storage, P3).
- Stdlib only for: `sqlite3`, `bz2`, `xml.etree.ElementTree` (iterparse),
  `hashlib`, `gzip`.
- Dev deps: `pytest>=8`, `pytest-cov`, `ruff>=0.5` (lint **and** format),
  `mypy>=1.10` (strict mode), `respx` (httpx mocking).
- Line length 100. `mypy --strict` on `src/`, relaxed on `tests/`.

**Desktop:**
- Tauri **v2** (Rust stable), React **18**, TypeScript strict, **Vite**, **pnpm**,
  **vitest**, state via **zustand**. No CSS framework decision imposed;
  plain CSS modules.
- Sidecar packaging: **PyInstaller** one-dir builds per OS/arch, bundled via
  Tauri `externalBin`.
- Engine↔UI protocol: **NDJSON JSON-RPC 2.0 over stdio** (spec in P6.1).

**Testing/CI:** GitHub Actions, matrix in P0.5. Coverage gate: 85% on
`engine/src/corpussieve/{domain,safety,contracts}`, 70% overall engine.

## 6. Phase and dependency graph

```text
P0 Foundations ──► P1 Source & Metadata ──► P2 Domain Compiler ──► P4 Extraction ──► P5 Exports
                                        └─► P3 LLM Assist ────────┘                     │
P6 Desktop App  (needs P1–P5 CLI/API surface)  ◄────────────────────────────────────────┘
P7 Purge & Release (needs P4 validation + P6 shell)
```

P3 may run in parallel with P4 after P2 completes. Everything else is sequential.

| Phase | File | Chunks | Design milestones |
|---|---|---|---|
| P0 Foundations & contracts | `P0_foundations.md` | P0.1–P0.6 | M0 |
| P1 Source inspection & metadata index | `P1_source_metadata.md` | P1.1–P1.6 | M1 |
| P2 Deterministic domain compiler | `P2_domain_compiler.md` | P2.1–P2.7 | M2 |
| P3 Local AI assistance | `P3_llm_assist.md` | P3.1–P3.6 | M3 |
| P4 Extraction & canonical corpus | `P4_extraction.md` | P4.1–P4.6 | M4 |
| P5 Normalization & exports | `P5_exports.md` | P5.1–P5.4 | M5 |
| P6 Desktop application | `P6_desktop.md` | P6.1–P6.7 | M6 |
| P7 Safe purge & release | `P7_purge_release.md` | P7.1–P7.4 | M7 |

## 7. Global Definition of Done (applies to every chunk, in addition to its own DoD)

```bash
cd engine && uv run ruff check . && uv run ruff format --check .
```
```bash
cd engine && uv run mypy src
```
```bash
cd engine && uv run pytest -q
```
(Frontend chunks additionally: `pnpm -C apps/desktop lint && pnpm -C apps/desktop test && pnpm -C apps/desktop build`.)
