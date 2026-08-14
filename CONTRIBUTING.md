# Contributing to CorpusSieve

Thank you for your interest in contributing to CorpusSieve!

## Developer Certificate of Origin (DCO) Sign-Off

To ensure legal compliance and clear licensing, CorpusSieve uses the Developer Certificate of Origin (DCO). All commits must include a `Signed-off-by` line in the commit message:

```text
Signed-off-by: Random J Developer <random@example.com>
```

You can automatically add this line to your commits using `git commit -s`.

---

## Chunk & Commit Conventions

CorpusSieve follows a strict execution work plan divided into phases and chunks.

1. **Commit Messages**: Format commit titles with the chunk ID prefix:
   ```text
   P1.3: categorylinks SQL ingestion
   ```
2. **Atomic Commits**: Each commit (or small series of commits) should address a single chunk or self-contained logical unit.
3. **Definition of Done**: Never mark a chunk complete or submit a pull request with failing lint, type checks, or tests.

---

## Architectural & Schema Changes

Per CorpusSieve design policies:

- **Architecture Decision Records (ADRs)**: Any architectural change, new external dependency, or modification to system boundaries requires an ADR proposal submitted to `docs/adr/`.
- **Schema Compatibility Notes**: Any modification to exported data contracts or JSON schemas requires a explicit backward-compatibility note and review to prevent breaking down-stream tools.

---

## Development Workflow

1. Fork and clone the repository.
2. Set up Python engine environment:
   ```bash
   cd engine
   uv sync
   ```
3. Verify your changes pass all quality gates before submitting:
   ```bash
   cd engine
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy src
   uv run pytest
   ```
