# Phase P0 — Foundations & Contracts (design milestone M0)

Goal: a compiling, linted, CI-green monorepo containing every frozen data
contract and the synthetic fixtures all later phases test against. No product
logic yet beyond contract validation.

---

## P0.1 Repo scaffold & tooling
**Depends:** none.

**Deliverables**
- Directory tree from Overview §3 (empty `__init__.py` files where needed).
- `engine/pyproject.toml` — hatchling; project name `corpussieve`, version
  `0.1.0.dev0`; deps and dev-deps exactly per Overview §5; console script
  `corpussieve = corpussieve.cli.main:app_entry`; ruff + mypy config
  (line length 100, `mypy --strict` for `src`).
- `engine/src/corpussieve/cli/main.py` — Typer app with the 8 command groups
  from the Naming Registry registered as empty sub-apps; `corpussieve --version`
  prints the version; `app_entry()` wraps `app()`.
- `.gitignore` (Python, Node, Rust, Tauri, PyInstaller, `.venv`, `dist`, `target`).
- `git init` on repo root; move `CorpusSieve_Solution_Design.md` to
  `docs/SOLUTION_DESIGN.md` (git mv after first commit is fine).
- `README.md` — product one-paragraph summary (from design §1), status banner
  "pre-release, under construction", dev setup (uv, pnpm, rust), repo map.

**Out of scope:** any domain logic; desktop app content (P6.2 scaffolds Tauri).

**DoD**
```bash
cd engine && uv sync && uv run corpussieve --version
```
```bash
cd engine && uv run corpussieve domain --help
```
Plus global DoD (Overview §7).

---

## P0.2 Governance & docs skeleton
**Depends:** P0.1.

**Deliverables**
- `LICENSE` (Apache-2.0, copyright "CorpusSieve contributors"), `NOTICE`.
- `CONTRIBUTING.md` — DCO sign-off model, chunk/commit conventions, "ADR
  required for architecture changes, compatibility note required for schema
  changes" (design §34).
- `SECURITY.md` — private reporting via GitHub security advisories; contact
  `support@intrepid.international`.
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1.
- `AGENTS.md` — for coding agents: points to `plan/00_OVERVIEW.md`, restates
  anti-drift rules §2, the frozen naming registry, and the DoD commands.
- `.github/ISSUE_TEMPLATE/` (bug, feature), `.github/PULL_REQUEST_TEMPLATE.md`.
- `docs/` stubs with real outlines (not lorem): `MVP_SPEC.md` (links FR-001…FR-030
  table copied from design §27), `DOMAIN_SPEC.md`, `DATA_CONTRACTS.md`,
  `UX_SPEC.md`, `TEST_STRATEGY.md`, `ROADMAP.md` (design §37 copied),
  `REFERENCES.md` (upstream URLs from design §39).
- Non-affiliation statement (Wikimedia/Ollama/LM Studio/AnythingLLM) in README
  and NOTICE.

**DoD:** files exist, README links resolve, global DoD passes.

---

## P0.3 Contracts — Pydantic models + exported JSON Schemas
**Depends:** P0.1. **This chunk freezes the contracts.**

**Deliverables** — `engine/src/corpussieve/contracts/`:

- `errors.py` — `ErrorCode(StrEnum)` with exactly the 16 codes of design §29;
  `CorpusSieveError(Exception)` carrying `code: ErrorCode`, `message`,
  `detail: dict`.
- `enums.py` — `JobState(StrEnum)` (Overview §4 list), `SelectionMode(StrEnum)`
  (`high_recall|balanced|high_precision`), `AmbiguousBranchPolicy(StrEnum)`
  (`include|exclude|review`), `MemberType(StrEnum)` (`page|subcat`),
  `BranchDecision(StrEnum)` (`include|exclude|review`).
- `source.py` — `SourceFileInfo` (name, path, size_bytes, mtime_iso,
  quick_hash), `SourceFingerprint` (project, language, dump_date | None,
  files: list[SourceFileInfo], fingerprint: str, official_checksum_verified:
  bool = False, full_hash: str | None), `SourceInspection` (adapter:
  Literal["wikimedia_xml_dump"], dump_kind: Literal["multistream","sequential"],
  has_multistream_index, has_page_sql, has_categorylinks_sql, warnings:
  list[str], fingerprint: SourceFingerprint).
  - `quick_hash` := hex SHA-256 over `first 64 KiB ∥ last 64 KiB ∥ size_bytes as
    8-byte big-endian`. `fingerprint` := hex SHA-256 of canonical JSON (sorted
    keys, `,`/`:` separators, UTF-8) of the files list. Implement
    `canonical_json_hash(obj) -> str` in `contracts/hashing.py`; reuse everywhere.
- `domain.py` — `DomainPolicy` (mode: SelectionMode = balanced,
  ambiguous_branch: AmbiguousBranchPolicy = review, max_total_categories: int =
  100_000, max_total_articles: int = 2_000_000, include_redirects: bool = False),
  `DomainRoot` (query: str, max_depth: int = 6), `DomainFacets`
  (include/exclude: list[str]), `DomainDefinition` (schema_version: Literal[1],
  id: slug pattern `^[a-z0-9][a-z0-9-]{1,62}$`, name, description, language,
  policy, facets, roots: min 1, hard_exclude_pages: list[str],
  forced_include_pages: list[str], exclude_categories: list[str] = []).
- `lock.py` — `ResolvedRoot` (query, resolved_category, max_depth),
  `CategoryDecision` (category, decision: BranchDecision, source:
  Literal["traversal","facet_exclude","llm","human"], confidence: float | None,
  reason: str, root: str | None, depth: int | None),
  `LlmProvenance` (provider, model_id, prompt_version, schema_version),
  `DomainLock` (schema_version: Literal[1], domain_id, domain_hash,
  source_fingerprint: str, resolved_roots, category_decisions,
  hard_exclude_pages, forced_include_pages, llm: LlmProvenance | None,
  compiler_version, compiled_at: ISO-8601 UTC, warnings_acknowledged: list[str],
  lock_hash: str). `lock_hash` = `canonical_json_hash` of the lock minus the
  `lock_hash` field itself.
- `manifest.py` — `SelectionReason` (root, depth, via_category, reason_type:
  Literal["category_path","forced_include"]), `ManifestRecord` (schema_version:
  Literal[1], project, language, page_id, title, namespace, selected: bool,
  selection: SelectionReason, revision_id/int|None, content_hash: str | None,
  document_id: str | None) — post-extraction fields optional, per design §12.
- `corpus.py` — `CorpusSource` (project, language, page_id, revision_id, title,
  source_url, dump_date | None), `CorpusRecord` (document_id
  `"{project}:{page_id}:{revision_id}"`, source: CorpusSource, categories:
  list[str], selection: SelectionReason, content: {format:
  Literal["wikitext"], raw: str}) — design §14.
- `project.py` — `ProjectFile` (schema_version: Literal[1], project_id, name,
  created_at, source_paths: list[str], source_adapter, source_fingerprint:
  str | None, workdir-relative paths for domain/lock/output, provider_ref:
  str | None, job_state: JobState = NEW). Explicit comment + validator: **no
  token/secret fields permitted** (design §21).
- `report.py` — `BuildReport` matching design §26 field-for-field (source
  fingerprint, corpussieve_version, domain_hash, lock_hash, model info,
  category totals {traversed, included, excluded, reviewed}, selected_articles,
  counts_by_root: dict, counts_by_depth: dict, forced counts, warnings,
  samples {included: list, borderline: list}, extraction_count,
  normalization_errors, output_bytes, validation: Literal["PASSED","FAILED",
  "NOT_RUN"], purge_eligible: bool).
- `providers.py` — `ModelInfo` (provider, model_id, loaded: bool, model_type:
  str | None, context_length: int | None, capability_result:
  Literal["passed","warn","failed","untested"]), `ProviderEndpoint` (provider:
  Literal["ollama","lmstudio"], base_url, is_loopback: bool, auth_token_ref:
  str | None — keyring reference, never the token).
- `llm_io.py` — structured-output contracts: `FacetProposal` (include/exclude
  facet lists + rationale), `BoundaryQuestion` (question, options,
  recommended, rationale), `BranchReviewResult` (decision, confidence: 0..1,
  reason, needs_human_review: bool) — design §11.5.
- `events.py` — `ProgressEvent` (job_id, stage, completed_units, total_units |
  None, message) — design §23.
- `export.py` — script `engine/scripts/export_schemas.py` writing
  `model_json_schema()` for: DomainDefinition, DomainLock, ManifestRecord,
  CorpusRecord, ProjectFile, BuildReport, BranchReviewResult, ProgressEvent to
  `schemas/<kebab-name>.schema.json` (sorted keys, trailing newline).
  Committed output must match regeneration (CI checks in P0.5).

**Tests** — `engine/tests/contracts/`: round-trip each model from a valid dict;
rejection tests (bad slug, unknown field — `model_config = ConfigDict(extra="forbid")`
on all models; confidence out of range); `canonical_json_hash` stability test
with a pinned expected hex digest; lock_hash excludes itself.

**DoD**
```bash
cd engine && uv run python scripts/export_schemas.py && git diff --exit-code ../schemas
```
Plus global DoD.

---

## P0.4 Synthetic fixture generator + golden fixtures
**Depends:** P0.3.

**Deliverables**
- `engine/tests/fixtures/generator.py` — deterministic (seeded) builder that
  emits a tiny fake wiki ("fixwiki", language `en`, dump date `20260801`) as
  real files under `engine/tests/fixtures/fixwiki/`:
  - `fixwiki-20260801-pages-articles-multistream.xml.bz2` — valid MediaWiki
    0.11 export XML, **multiple independent bz2 streams**, ≤10 pages per
    stream, ~60 pages total.
  - `fixwiki-20260801-pages-articles-multistream-index.txt.bz2` — real
    `offset:page_id:title` lines matching the streams.
  - `fixwiki-20260801-pages-articles.xml.bz2` — same pages, single stream.
  - `fixwiki-20260801-page.sql.gz` and `fixwiki-20260801-categorylinks.sql.gz`
    — genuine MediaWiki-style `INSERT INTO \`page\` VALUES (...),(...);` dumps
    consistent with the XML.
- Fixture content MUST cover (design §32 golden list): a category cycle
  (`A→B→C→A`); redirects; a page reachable via two roots; an excluded subtree
  reachable from another root; Unicode titles (e.g. `Pokémon_(fixture)`,
  `日本のゲーム`); malformed wikitext page; non-zero namespaces (Talk, Category,
  Template); a category whose growth explodes (for runaway tests). Encode the
  expected ground truth in `engine/tests/fixtures/fixwiki/expected.json`
  (which pages a "video games"-like domain selects, counts per depth).
- Fixture files are committed (small, <200 KiB total). Regeneration is
  deterministic: running the generator reproduces byte-identical files.
- `examples/domains/video-games.yaml` — the design §11.2 example, valid
  against `DomainDefinition`.

**DoD**
```bash
cd engine && uv run python tests/fixtures/generator.py && git diff --exit-code tests/fixtures/fixwiki
```
```bash
cd engine && uv run pytest tests/fixtures -q
```

---

## P0.5 CI workflows
**Depends:** P0.1–P0.4.

**Deliverables** — `.github/workflows/`:
- `engine.yml` — matrix {ubuntu-latest, macos-latest, windows-latest} ×
  py3.12: uv sync, ruff check + format check, mypy, pytest with coverage
  gates (Overview §5), schema regeneration diff check, fixture regeneration
  diff check.
- `desktop.yml` — pnpm install, lint, vitest, `tauri build --debug` on the
  3-OS matrix. **Until P6.2 exists**, the workflow must detect the absence of
  `apps/desktop/package.json` and exit 0 with a notice (so CI is green from P0).
- `schemas.yml` — on PR touching `schemas/` or `contracts/`: regeneration
  check + a compatibility job that fails if a previously-required field was
  removed (simple JSON diff script `engine/scripts/schema_compat.py`).

**DoD:** `git push` to a branch shows all workflows green (or run
`act`-equivalent local dry-run if no remote is configured; record which in
PROGRESS.md).

---

## P0.6 ADRs 0001–0006
**Depends:** P0.2.

**Deliverables** — `docs/adr/` using MADR-lite template (`NNNN-title.md`,
Status/Context/Decision/Consequences), one per design §35:
0001 Tauri v2 + packaged Python sidecar; 0002 deterministic core, advisory
LLM; 0003 non-destructive build + separate verified purge; 0004 domain
definition + source-specific lock; 0005 canonical corpus independent of
consumers; 0006 API-based model discovery, no shell discovery. Each Decision
section must cite the concrete pinned choices from Overview §5 where relevant.

**DoD:** 6 files exist, linked from `docs/SOLUTION_DESIGN.md` header note and
README; global DoD.
