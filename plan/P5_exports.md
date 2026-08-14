# Phase P5 — Normalization & Exports (design milestone M5)

Goal: turn the canonical corpus into RAG-ready Markdown and developer JSONL
with attribution (FR-022, FR-030). Exports read **only** the canonical corpus
directory — never the source dump (design §14: regenerable without re-reading
the dump).

---

## P5.1 Normalizer interface + wikitext→markdown
**Depends:** P4.5.

**Deliverables**
- `normalization/base.py` — `Normalizer(Protocol)`:
  `normalize(record: CorpusRecord) -> NormalizedDoc` where `NormalizedDoc` =
  (title, frontmatter: dict, markdown: str, warnings: list[str]).
  Registry `get_normalizer(name: str = "wikitext-md-v1")`.
- `normalization/wikitext_md.py` — `WikitextMarkdownNormalizer` using
  `mwparserfromhell` (behind the interface; tests pin **output**, not parser
  internals — design §15.1):
  - Headings `== X ==` → `## X` (level n → n `#`s, min 2; article title is
    the single `# H1`).
  - Wikilinks `[[Target|label]]` → `label` plain text (`[[Target]]` → `Target`);
    category/file/interwiki links dropped.
  - External links → `label` text only.
  - Templates: dropped, except `{{Infobox …}}` → a `**Facts**` bullet list of
    scalar `|key=value` params when all values are plain text; otherwise
    dropped with warning `infobox_skipped`.
  - `<ref>…</ref>` and reference sections (`== References/External links/
    See also/Further reading ==` and content under them) removed entirely
    ("handle references consistently": policy = drop, recorded once here).
  - Lists `*`/`#` → `-` / `1.`; bold/italic quotes → `**`/`*`; tables →
    GitHub tables when rectangular and ≤ 8 columns, else dropped with warning
    `table_skipped`.
  - HTML comments, `__MAGICWORDS__`, nav templates removed.
  - Malformed wikitext must never raise: catch parser errors → return raw
    text stripped of markup chars + warning `parse_degraded`.
- Golden tests: `tests/normalization/golden/*.wiki` + `*.md` pairs (≥10
  cases incl. the fixture's malformed page, Unicode, infobox, nested
  templates, table). Test compares exact output.

**DoD:** global DoD; golden suite passes.

---

## P5.2 Markdown exporter
**Depends:** P5.1.

**Deliverables** — `exporters/markdown.py`:
- `export_markdown(corpus_dir, output_dir, events) -> ExportSummary`:
  one `.md` per article, YAML frontmatter exactly per design §15.1 (source,
  project, language, title, page_id, revision_id, license `CC BY-SA 4.0`)
  followed by normalized markdown.
- Filenames: `f"{page_id}-{slugify(title)[:80]}.md"`; `slugify` in
  `exporters/naming.py` — NFC normalize, keep `[A-Za-z0-9._-]`, collapse `-`;
  **path-traversal safe by construction** (no `/`, no leading `.`, tested with
  hostile titles `../../etc/passwd`, `CON`, trailing dot — Windows-reserved
  names get `_` suffix) — design §24 untrusted-content rules.
- Layout: flat dir + `_index.json` (document_id → filename map);
  normalization warnings aggregated into `ExportSummary.normalization_errors`
  (fed back into build-report update).
- Staging + atomic promote, same pattern as P4.5.

**Tests:** fixture corpus export → file count, one golden file byte-compare,
hostile-title safety, `_index.json` completeness.

**DoD:** global DoD.

---

## P5.3 JSONL exporter + attribution
**Depends:** P4.5.

**Deliverables**
- `exporters/jsonl.py` — `export_jsonl(corpus_dir, output_dir,
  normalized: bool)`: re-emit canonical records (raw) or NormalizedDoc-based
  records (normalized) as plain `.jsonl` (uncompressed, for downstream tools)
  with the same record schemas.
- `exporters/attribution.py` — writes `ATTRIBUTION.md` (human-readable: source
  project, dump date, license statement, per design §25 including the
  non-affiliation and user-responsibility statements) and machine-readable
  `attribution.json` (already drafted in P4.5 — this chunk finalizes: one
  entry per document: title, page_id, revision_id, source_url, license).
  Both markdown and jsonl exporters call this; every export directory contains
  both files (acceptance criterion 18).

**Tests:** attribution completeness = corpus count; license string exact;
JSONL round-trip parse.

**DoD:** global DoD.

---

## P5.4 CLI: `export` + AnythingLLM ingestion guide
**Depends:** P5.2, P5.3.

**Deliverables**
- `cli/export_cmds.py` —
  `corpussieve export markdown --corpus DIR --output DIR2 [--json]`,
  `corpussieve export jsonl --corpus DIR --output DIR2 [--normalized] [--json]`.
  State → EXPORTED. Progress + summary rendering per CLI conventions.
- `docs/ANYTHINGLLM.md` — step-by-step guide: export markdown → AnythingLLM
  workspace → upload folder → embed (screenshot-free, version-tolerant
  wording); linked from README. Explicitly notes API integration is post-MVP
  and CorpusSieve never touches AnythingLLM's storage directory (design §15.3).

**Tests:** CliRunner both exporters end-to-end on fixture corpus.

**DoD**
```bash
cd engine && uv run corpussieve export markdown --corpus /tmp/fixcorpus/corpus --output /tmp/fixmd --json
```
Plus global DoD. **Phase gate:** acceptance criteria 13, 18 true on fixtures.
