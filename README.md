# CorpusSieve

> **Status:** pre-release, under construction

CorpusSieve is a lightweight, local-first engine for distilling massive dumps into topic-specific, deterministic Wikitext corpora for local AI and fine-tuning. It compiles large MediaWiki source dumps into verified, topic-focused corpora using a category graph compiler, optional local AI assistance, and multistream extraction.

---

## Non-Affiliation Notice

CorpusSieve is an independent open-source project and is **not affiliated with, endorsed by, or sponsored by** the Wikimedia Foundation, Ollama, LM Studio, AnythingLLM, or any of their respective parent companies or trademarks.

---

## Developer Setup

### Prerequisites

- **Python**: 3.12 or higher (managed via [`uv`](https://github.com/astral-sh/uv))
- **Node.js**: Node 18+ and [`pnpm`](https://pnpm.io/) (for desktop application in `apps/desktop`)
- **Rust**: Stable Rust toolchain (for Tauri v2 desktop shell)

### Engine Development

1. Install dependencies and set up virtual environment:
   ```bash
   cd engine
   uv sync
   ```

2. Run CLI commands:
   ```bash
   uv run corpussieve --version
   uv run corpussieve --help
   ```

3. Code Quality & Testing:
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy src
   uv run pytest
   ```

---

## Repository Structure

```text
.
├── README.md                 # Product overview and developer guide
├── LICENSE / NOTICE          # Governance and copyright notice
├── plan/                     # Execution plan and progress tracking
├── docs/                     # Documentation, specs, and Architecture Decision Records (ADRs)
│   ├── SOLUTION_DESIGN.md    # CorpusSieve solution design document
│   └── adr/                  # ADRs 0001-0006 (Architecture Decision Records)
├── engine/                   # Python core engine & CLI binary (`corpussieve`)
│   ├── pyproject.toml
│   ├── src/corpussieve/
│   │   ├── cli/              # Typer CLI sub-commands
│   │   ├── api/              # Engine protocol server
│   │   ├── contracts/        # Pydantic v2 data models and contracts
│   │   ├── sources/          # Source adapters (MediaWiki XML/SQL)
│   │   ├── metadata/         # Metadata index build & queries
│   │   ├── domain/           # Deterministic category compiler & traversal engine
│   │   ├── models/           # Local AI provider adapters (Ollama, LM Studio)
│   │   ├── extraction/       # Multistream & sequential extraction engines
│   │   ├── normalization/    # Text normalizer (wikitext to markdown)
│   │   ├── validation/       # Corpus build validation & report generation
│   │   ├── exporters/        # Markdown & JSONL exporters
│   │   ├── safety/           # Preconditions & safe purge executors
│   │   └── jobs/             # Job state machine & event dispatcher
│   └── tests/                # Test suite and synthetic fixtures
├── schemas/                  # Exported JSON Schemas
├── examples/domains/         # Example domain definition files
└── apps/desktop/             # Tauri v2 + React desktop application
```
