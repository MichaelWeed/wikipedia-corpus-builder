# Phase P1 — Source Inspection & Metadata Index (design milestone M1)

Goal: point CorpusSieve at a local dump directory, understand what's there,
fingerprint it, and build the on-disk SQLite metadata index that the domain
compiler queries. Covers FR-001, FR-002, FR-003, FR-004 and the `source`/
`metadata` CLI groups.

All file reads in this phase are streaming; nothing loads a whole dump or SQL
file into memory (design §10, §28).

---

## P1.1 Source layer skeleton + filename/dump-type detection
**Depends:** P0.3, P0.4.

**Deliverables**
- `sources/base.py` — `SourceAdapter(ABC)` with the design §9.2 surface:
  `inspect() -> SourceInspection`, `fingerprint() -> SourceFingerprint`,
  `build_metadata_index(db_path: Path, progress: Callable[[ProgressEvent], None]) -> None`,
  `enumerate_pages() -> Iterator[RawPage]`,
  `extract_selected_pages(page_ids: set[int], progress) -> Iterator[RawPage]`,
  `source_metadata() -> dict`. `RawPage` dataclass: page_id, namespace, title,
  revision_id, redirect_target: str | None, wikitext: str.
- `sources/wikimedia/naming.py` —
  `parse_dump_filename(name: str) -> DumpNameParts | None` where
  `DumpNameParts` = (project e.g. `enwiki`/`fixwiki`, language guess = project
  minus trailing `wiki`, date `YYYYMMDD`, kind). Recognize exactly:
  `{proj}-{date}-pages-articles-multistream.xml.bz2`,
  `…-multistream-index.txt.bz2`, `{proj}-{date}-pages-articles.xml.bz2`,
  `{proj}-{date}-page.sql.gz`, `{proj}-{date}-categorylinks.sql.gz`.
  Unknown names → None (never guess).
- `sources/wikimedia/adapter.py` — `WikimediaXmlDumpAdapter(source: Path)`
  accepting a file **or** directory. `inspect()`: locate companions in the same
  directory by naming; set `dump_kind` multistream only when the index file is
  present; emit warnings (`SOURCE_COMPANION_MISSING` semantics, not exceptions)
  when index/page.sql/categorylinks.sql are absent; raise
  `CorpusSieveError(SOURCE_UNSUPPORTED)` when no recognizable dump exists.
  `enumerate_pages` / `extract_selected_pages` raise NotImplementedError until
  P4 (allowed stub, listed here).
- Post-MVP adapter stubs (empty classes raising NotImplementedError with a
  "post-MVP" message): `MediaWikiContentExportAdapter`,
  `WikimediaEnterpriseSnapshotAdapter`, `WikimediaStructuredContentsAdapter`
  in `sources/future.py`.

**Tests** — `tests/sources/test_naming.py` (each pattern, rejection of near-misses),
`tests/sources/test_inspect.py` against fixwiki fixtures (multistream detected,
sequential fallback detected, missing-companion warnings, unsupported dir).

**DoD:** global DoD; inspection of `tests/fixtures/fixwiki` returns
`dump_kind="multistream"` with zero warnings.

---

## P1.2 Source fingerprinting
**Depends:** P1.1.

**Deliverables**
- `sources/fingerprint.py` — `fingerprint_files(paths: list[Path]) -> SourceFingerprint`
  implementing the P0.3 quick-hash spec; optional
  `full_hash(paths, progress) -> str` (streamed SHA-256, 1 MiB chunks) behind
  an explicit flag — never run implicitly.
- Adapter `fingerprint()` wires this over the dump + companions found by inspect.
- Drift check helper `fingerprints_match(a, b) -> bool` comparing the
  `fingerprint` digest only (used later by purge preconditions P7.1).

**Tests:** stable digest across two runs; digest changes when one byte of a
fixture copy changes (copy fixture to tmp, flip a byte); mtime change alone
does NOT change `fingerprint` (mtime is recorded but excluded from the hashed
canonical JSON — put it in a non-hashed field; adjust `SourceFileInfo` docs
accordingly — this is the one sanctioned contract clarification, note it in
PROGRESS.md).

**DoD:** global DoD.

---

## P1.3 SQL dump parser (page, categorylinks)
**Depends:** P1.1.

**Deliverables**
- `metadata/sqlparse.py` — a streaming parser for MediaWiki `*.sql.gz` dumps.
  `iter_insert_tuples(path: Path, table: str) -> Iterator[tuple]`:
  reads gzip text incrementally, finds ``INSERT INTO `table` VALUES`` statements,
  and yields each parenthesized tuple as Python values. Must implement a
  character-level state machine handling: single-quoted strings with `\'`,
  `\\`, `\"` escapes; NULL; integers; floats; binary/hex literals passed
  through as str. No regex-splitting on commas. No MySQL server involved.
- `metadata/rows.py` — typed extractors:
  `iter_page_rows(path) -> Iterator[PageRow]` mapping columns
  (page_id, page_namespace, page_title, page_is_redirect) by MediaWiki column
  position, tolerant of trailing extra columns;
  `iter_categorylinks_rows(path) -> Iterator[CategoryLinkRow]` mapping
  (cl_from, cl_to, cl_type) with cl_type normalized to `MemberType`
  (`page`/`subcat`; `file` rows are skipped and counted).
  Titles are stored with underscores exactly as in the dump; define
  `normalize_title(t: str) -> str` (spaces→underscores, first char uppercased
  per MediaWiki semantics, strip) in `metadata/titles.py` and use it at every
  comparison boundary from now on.

**Tests:** parse fixwiki SQL fixtures and compare against `expected.json`;
adversarial unit strings (escaped quote inside title, `'a''b'` not valid MySQL
— ensure documented behavior, Unicode, tuple spanning buffer boundary — test
with a 64-byte read buffer).

**DoD:** global DoD; parsing fixwiki `categorylinks` yields the exact
row count recorded in `expected.json`.

---

## P1.4 Metadata SQLite index build
**Depends:** P1.3.

**Deliverables**
- `metadata/schema.sql` — exactly the design §10 tables (`pages`,
  `category_membership`, `categories`, `category_edges`, `domain_decisions`)
  plus `meta(key TEXT PRIMARY KEY, value TEXT)` for
  {schema_version=1, source_fingerprint, built_at, corpussieve_version}.
  Indexes: `category_edges(parent_category)`, `category_membership(category)`,
  `category_membership(page_id)`, `pages(title)`, `categories(category)`
  and an FTS5-free prefix search support index `categories(category COLLATE NOCASE)`.
- `metadata/build.py` — `build_metadata_index(adapter, db_path, progress)`:
  streams P1.3 iterators into SQLite with executemany batches of 5 000 rows,
  single transaction per batch, `PRAGMA journal_mode=WAL`,
  `PRAGMA synchronous=NORMAL`. Derivation rules:
  - `pages` ← page rows (all namespaces kept; namespace filter happens at query
    time).
  - `category_membership` ← categorylinks rows where cl_type=`page`, joined via
    cl_from → page. `member_type` column stores the raw type.
  - `category_edges` ← categorylinks rows where cl_type=`subcat`:
    parent = cl_to, child = title of the page cl_from (namespace 14), resolved
    via the pages table.
  - `categories` ← distinct cl_to values ∪ namespace-14 pages (page_id filled
    when a category page exists).
  Emits `ProgressEvent(stage="metadata", …)` every batch. Build is atomic:
  write to `<db>.building`, fsync, rename over target on success; a crashed
  build leaves no half-valid `metadata.sqlite`.
  Raise `CorpusSieveError(METADATA_PARSE_FAILED)` on parser errors, with file
  + approximate offset in detail.

**Tests:** end-to-end build from fixwiki; row counts vs `expected.json`;
rebuild is idempotent (same table contents); crash simulation (kill after N
batches via injected callback) leaves only the `.building` file.

**DoD:** global DoD; fixwiki index builds in <5 s.

---

## P1.5 Metadata query API
**Depends:** P1.4.

**Deliverables** — `metadata/queries.py`, class `MetadataIndex(db_path)`
(read-only connection, context manager):
- `child_categories(category: str) -> list[str]`
- `member_page_ids(category: str, namespaces: tuple[int, ...] = (0,)) -> list[int]`
- `categories_of_page(page_id: int) -> list[str]`
- `search_categories(query: str, limit: int = 25) -> list[CategoryHit]` —
  case-insensitive substring on normalized title; `CategoryHit` = (category,
  direct_page_count, subcat_count); exact-match ranks first, then by
  direct_page_count desc.
- `page_by_title(title: str) -> PageRow | None`, `pages_by_ids(ids) -> …`
- `category_exists(category: str) -> bool`
- `stats() -> MetadataStats` (page/category/edge counts, source_fingerprint,
  built_at).
- `record_domain_decision(…)` / `get_domain_decisions(domain_hash,
  source_fingerprint)` over `domain_decisions` (used by P3.6).

**Tests:** every method against fixwiki with expected values; search ranking
test; read-only enforcement (writes raise).

**DoD:** global DoD.

---

## P1.6 CLI: `source inspect`, `metadata build`, `metadata search`
**Depends:** P1.5, P1.2.

**Deliverables** — `cli/source_cmds.py`, `cli/metadata_cmds.py`:
- `corpussieve source inspect --source PATH [--json]` — renders a Rich table
  (files found, sizes, dump kind, warnings) or the `SourceInspection` JSON.
  Exit 0 on success incl. warnings; exit 2 with `SOURCE_UNSUPPORTED` payload on
  unrecognizable source.
- `corpussieve metadata build --source PATH --project-dir DIR [--json]` —
  runs P1.4 into `DIR/cache/metadata.sqlite`, Rich progress bar from
  ProgressEvents, writes/updates `DIR/project.yaml` (creating a minimal
  ProjectFile when absent; state transitions NEW→SOURCE_INSPECTED→
  METADATA_INDEXING→METADATA_READY).
- `corpussieve metadata search --project-dir DIR QUERY [--json]`.
- CLI-wide conventions (frozen now, all later commands follow):
  `--json` machine output on stdout only; human output via Rich to stderr-safe
  console; exit codes: 0 ok, 2 CorpusSieveError (payload
  `{"error": {"code": …, "message": …, "detail": …}}`), 3 unexpected exception
  (logged with stack to `DIR/reports/last-error.log`, never raw-dumped in
  non-expert output; `--debug` prints it). Implement once in
  `cli/_runner.py::run_command(fn)`.

**Tests:** `typer.testing.CliRunner` tests for each command incl. `--json`
schema-validity and exit codes.

**DoD**
```bash
cd engine && uv run corpussieve source inspect --source tests/fixtures/fixwiki --json
```
```bash
cd engine && uv run corpussieve metadata build --source tests/fixtures/fixwiki --project-dir /tmp/fixproj && uv run corpussieve metadata search --project-dir /tmp/fixproj games
```
Plus global DoD.
