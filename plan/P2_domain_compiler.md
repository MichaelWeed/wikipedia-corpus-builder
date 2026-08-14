# Phase P2 — Deterministic Domain Compiler (design milestone M2)

Goal: from a hand-written `domain.yaml`, deterministically resolve roots
against the local metadata index, traverse the category graph safely, produce a
manifest with provenance, a preview, and a reproducible `domain.lock.json` —
**with no LLM anywhere** (FR-005, FR-007, FR-012–FR-014, FR-016–FR-018).
P3 plugs into the extension points defined here; it must not change them.

Determinism invariant for the whole phase: same metadata.sqlite + same
domain.yaml + same compiler version ⇒ byte-identical lock (except `compiled_at`)
and identical manifest ordering (sorted by page_id).

---

## P2.1 Domain definition load/validate + `domain create`
**Depends:** P1.6.

**Deliverables**
- `domain/definition.py` — `load_domain(path) -> DomainDefinition` (YAML →
  model, `extra="forbid"`; errors wrapped as CorpusSieveError with YAML line
  info where available), `save_domain(defn, path)` (stable key order matching
  the P0.3 model field order), `domain_hash(defn) -> str` via
  `canonical_json_hash`.
- `cli/domain_cmds.py::create` — `corpussieve domain create --id ID --name NAME
  --language LANG --project-dir DIR [--intent TEXT]` writes a template
  `DIR/domains/<id>.yaml` with commented guidance. `--intent` is **stored
  verbatim** in `description` for now; a note in `--help` says LLM-assisted
  intent compilation arrives with `model` configuration (P3.5 upgrades this
  command; the flag and storage behavior here are forward-compatible on purpose).

**Tests:** load/save round-trip preserves content; invalid YAML/fields produce
line-annotated errors; hash stable across key re-ordering of input YAML.

**DoD:** global DoD; `domain create` then `load_domain` succeeds on output.

---

## P2.2 Root resolution against local categories
**Depends:** P2.1.

**Deliverables** — `domain/resolve.py`:
- `resolve_roots(defn, index: MetadataIndex) -> RootResolution` where
  `RootResolution` = (resolved: list[ResolvedRoot], unresolved: list[str],
  candidates: dict[query, list[CategoryHit]]).
  Rule (FR-012, "never trust invented names"): a root query resolves iff
  `category_exists(normalize_title(query))` — exact normalized match only.
  Non-exact search hits are returned as `candidates` for the caller/UI to
  offer; the compiler itself never auto-picks a fuzzy match.
- `resolve_exclusions(defn, index)` — same exact-match rule for
  `exclude_categories`; facet strings (`facets.exclude`) are matched against
  category titles by normalized substring to build the *facet-derived* excluded
  set, each recorded as `CategoryDecision(source="facet_exclude")`.
- Unresolved root ⇒ `CorpusSieveError(DOMAIN_ROOT_UNRESOLVED)` listing
  candidates in detail (CLI renders them as suggestions).

**Tests:** fixwiki exact resolution; unresolved with candidate suggestions;
Unicode root; facet-exclusion set matches `expected.json`.

**DoD:** global DoD.

---

## P2.3 Category graph traversal engine
**Depends:** P2.2. **This is the core algorithm — implement exactly.**

**Deliverables** — `domain/traverse.py`:
- `traverse(index, resolved_roots, excluded: set[str], policy: DomainPolicy,
  on_ambiguous: AmbiguousHook | None = None) -> TraversalResult`.
- Algorithm (frozen semantics, design §11.4):
  - BFS per root, roots processed in lock order; global
    `visited: dict[category, (root, depth)]` — first visit wins provenance;
    a category is expanded at most once globally.
  - Depth: root category = depth 0; children via `category_edges` = parent
    depth + 1; never expand beyond that root's `max_depth`.
  - A category in the excluded set is recorded as
    `CategoryDecision(decision=exclude)` and **not expanded**, but this does
    not retroactively remove pages reached via other included categories.
  - Cycle safety: the visited map makes revisits no-ops; assert no category is
    expanded twice (test-visible counter).
  - Runaway guard: if included categories exceed `policy.max_total_categories`,
    abort with `CorpusSieveError(DOMAIN_RUNAWAY_GROWTH)` carrying the last 20
    expanded categories in detail. Additionally compute per-expansion growth:
    if a single category adds > 5 000 children, record a warning
    `explosive_growth:<category>`.
  - `on_ambiguous` hook: called for each candidate child NOT matched by any
    include facet substring and not excluded, **only when**
    `policy.ambiguous_branch == review`. Signature
    `(ctx: AmbiguousBranchContext) -> BranchDecision` where ctx = (domain
    definition, root, parent_path: list[str], candidate, sample_children:
    ≤10 names, sample_members: ≤10 titles). Default hook (this phase):
    mode-based — high_recall→include, balanced→include+warning
    `unreviewed_branch:<category>`, high_precision→exclude. P3.6 substitutes
    an LLM-backed hook; P6 substitutes a human-queue hook. The traversal
    engine itself never knows which.
  - Deterministic ordering: children expanded in sorted(title) order.
- `TraversalResult` = (decisions: list[CategoryDecision], included:
  set[str] categories, warnings: list[str], stats: counts by depth/root).

**Tests (golden, against fixwiki `expected.json`):** cycle terminates; depth
boundary exact (page at depth == max_depth included, max_depth+1 not);
excluded-subtree-reachable-via-other-root page still included with correct
provenance; runaway triggers on the explosive fixture with a low limit; all
three default ambiguous modes; determinism (two runs, identical decision list).

**DoD:** global DoD; 100% branch coverage on `traverse.py`
(`uv run pytest --cov=corpussieve.domain.traverse --cov-branch` ≥ 100%).

---

## P2.4 Article selection + manifest generation
**Depends:** P2.3.

**Deliverables** — `domain/select.py`:
- `select_articles(index, traversal: TraversalResult, defn) ->
  Iterator[ManifestRecord]`:
  union of `member_page_ids(cat, namespaces=(0,))` over included categories;
  redirects excluded unless `policy.include_redirects`; provenance = the
  including category with the smallest (depth, category) — deterministic;
  then apply `forced_include_pages` (must resolve by exact title via
  `page_by_title`, else warning `forced_include_unresolved:<title>`) with
  `reason_type="forced_include"`; then remove `hard_exclude_pages` (exact
  title match) — hard exclude beats forced include, and the collision emits
  warning `exclude_overrides_force:<title>`.
  Output sorted by page_id. Enforce `policy.max_total_articles` →
  `DOMAIN_RUNAWAY_GROWTH`.
- `domain/manifest_io.py` — `write_manifest(records, path)` /
  `read_manifest(path)` as zstd-compressed JSONL of `ManifestRecord`
  (level 10, one JSON object per line, sorted keys).

**Tests:** fixture ground truth counts; forced/hard precedence matrix (4
cases); redirect policy both ways; multi-path page provenance is the
min-(depth,category) one; manifest round-trip.

**DoD:** global DoD.

---

## P2.5 Domain lock generation (deterministic path)
**Depends:** P2.4.

**Deliverables** — `domain/lock_build.py`:
- `compile_lock(defn, index, source_fingerprint, on_ambiguous=None,
  llm_provenance=None, acknowledged_warnings=()) -> tuple[DomainLock,
  TraversalResult]` — orchestrates resolve → traverse → decisions;
  `compiler_version` = package version; `llm` None on this path.
- `verify_lock(lock, defn, source_fingerprint) -> list[str]` — mismatched
  domain_hash, mismatched fingerprint, tampered lock_hash → hard errors
  (used by build in P4 and purge in P7: **build consumes the lock and never
  re-decides**, design §11.3).
- `write_lock/read_lock` JSON with sorted keys + trailing newline.

**Tests:** recompile determinism (identical lock_hash, `compiled_at` masked);
verify_lock catches each tamper class (edit a decision, change fingerprint,
change definition).

**DoD:** global DoD.

---

## P2.6 Preview & audit
**Depends:** P2.5.

**Deliverables** — `domain/preview.py`:
- `build_preview(index, lock, traversal, records) -> DomainPreview` (new
  contract in `contracts/preview.py`, sanctioned addition): article_count,
  estimated_output_bytes (mean wikitext size heuristic: 3 500 bytes/article ×
  count — constant named `EST_BYTES_PER_ARTICLE`), counts_by_root,
  counts_by_depth, sample_included (deterministic: 10 pages with seed =
  int(lock.lock_hash[:8], 16)), sample_borderline (pages whose provenance
  depth == root max_depth), contamination_groups (included categories whose
  title matches a facets.exclude substring — "suspected contamination"),
  warnings (from traversal + `selection_too_broad` when article_count >
  50% of namespace-0 pages, `selection_probably_incomplete` when < 5 pages).
- `explain_page(index, lock, records, title_or_id) -> ExplainResult` — the
  "why included?" answer: provenance chain root→…→via_category, or the
  nearest excluded ancestor when not selected.

**Tests:** fixture-pinned preview values; explain for an included, an
excluded-by-branch, and an absent page.

**DoD:** global DoD.

---

## P2.7 CLI: `domain compile`, `domain audit`, `domain preview`
**Depends:** P2.6.

**Deliverables** — extend `cli/domain_cmds.py` (all follow P1.6 conventions):
- `corpussieve domain compile --domain PATH --project-dir DIR [--json]` →
  writes `<domain>.lock.json` next to the YAML, updates project state
  DOMAIN_DRAFT→DOMAIN_COMPILED, prints decision/warning summary. Unresolved
  roots exit 2 with candidate suggestions rendered.
- `corpussieve domain preview --domain PATH --project-dir DIR [--json]` →
  compiles (or reuses fresh lock), writes manifest to
  `DIR/cache/manifest.preview.jsonl.zst`, renders DomainPreview; state → PREVIEWED.
- `corpussieve domain audit --domain PATH --project-dir DIR [--page TITLE_OR_ID]
  [--json]` → lock verification result + `explain_page` when `--page` given.

**Tests:** CliRunner flows over fixwiki end-to-end (create → edit fixture
domain → compile → preview → audit), `--json` outputs validate against
schemas.

**DoD**
```bash
cd engine && uv run corpussieve domain compile --domain ../examples/domains/video-games.yaml --project-dir /tmp/fixproj --json
```
(using the fixwiki-adapted example domain committed in P0.4) plus global DoD.
