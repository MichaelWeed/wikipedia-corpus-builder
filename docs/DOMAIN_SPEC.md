# CorpusSieve — Domain Compiler Specification (DOMAIN_SPEC)

The Domain Compiler is responsible for converting a high-level `DomainDefinition` into a fully resolved, reproducible `DomainLock`.

## Architecture & Traversal

1. **Domain Definition (`domain.yaml`)**:
   - `schema_version`: `1`
   - `id`: Unique slug (`^[a-z0-9][a-z0-9-]{1,62}$`)
   - `policy`: Mode (`high_recall`, `balanced`, `high_precision`), max categories, max articles, redirects flag
   - `roots`: List of category query roots (`query`, `max_depth`)
   - `facets`: Include/exclude keyword facets
   - `hard_exclude_pages` & `forced_include_pages`: Page override rules

2. **Graph Traversal Engine**:
   - Reads category relationships from indexed SQLite database (`cache/metadata.sqlite`).
   - Breadth-first traversal starting from root categories up to `max_depth`.
   - Cycle detection via visited category set.
   - Evaluates category inclusion via deterministic rule engine (facet matching, selection policy) and optional advisory LLM branch review.

3. **Domain Lock (`domain.lock.json`)**:
   - Immutable artifact containing resolved category decisions and page selections.
   - Cryptographically hashed (`lock_hash`) for build reproducibility.
