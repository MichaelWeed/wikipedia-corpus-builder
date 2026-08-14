# Phase P4 — Extraction & Canonical Corpus (design milestone M4)

Goal: consume a verified lock + manifest and produce the validated canonical
corpus from a real dump — multistream selective extraction, sequential
fallback, checkpoint/resume, job state machine, validation, build report
(FR-019–FR-021, FR-023–FR-025). The source is opened read-only; nothing in
this phase writes to or deletes any source file.

Memory rule for the whole phase: streaming only; no structure sized by the
whole dump may be held in RAM except the selected page_id set and the
(offset→page_ids) group map.

---

## P4.1 Job state machine + checkpoint store
**Depends:** P2.5.

**Deliverables**
- `jobs/state.py` — `JobStore(state_sqlite_path)` with tables
  `jobs(job_id TEXT PK, kind TEXT, state TEXT, created_at, updated_at,
  lock_hash TEXT, error_code TEXT NULL, error_message TEXT NULL)` and
  `checkpoints(job_id, seq INTEGER, payload_json TEXT, created_at,
  PRIMARY KEY(job_id, seq))`. API: `create_job(kind, lock_hash)`,
  `transition(job_id, new_state)` — enforcing exactly the design §22 graph
  (illegal transition raises; `FAILED`/`CANCELLED` reachable from any active
  state), `save_checkpoint(job_id, payload)`, `latest_checkpoint(job_id)`,
  `active_job(kind)`.
  Crash rule (design §22): on open, any job left in an active state
  (`BUILDING`, `VALIDATING`, `METADATA_INDEXING`) is marked
  `interrupted=1`, surfaced as resumable — never reported as complete.
- `jobs/events.py` — `EventBus` fanning `ProgressEvent` to callbacks (CLI
  Rich progress now; engine protocol in P6.1). Events emitted at least once
  per checkpoint unit.
- Sync `ProjectFile.job_state` with the job store on every transition.

**Tests:** full legal-path walk; every illegal transition rejected;
interrupted-job detection after simulated crash; checkpoint round-trip.

**DoD:** global DoD.

---

## P4.2 Multistream index parsing + stream grouping
**Depends:** P1.1.

**Deliverables** — `extraction/multistream_index.py`:
- `iter_index(path) -> Iterator[IndexEntry]` — streams the bz2 index; lines
  are `offset:page_id:title`; title may contain `:` — split max 2. Malformed
  line → `CorpusSieveError(EXTRACTION_PARSE_FAILED)` with line number.
- `group_selected(index_path, selected_ids: set[int]) -> StreamPlan` —
  `StreamPlan.groups: list[StreamGroup(offset, next_offset | None,
  page_ids: list[int])]`, only offsets containing ≥1 selected page, sorted by
  offset; `next_offset` = next distinct offset in the file (None for last),
  giving the byte range `[offset, next_offset)` of each bz2 stream.
  Also returns `missing_ids` (selected ids absent from the index) — reported
  as warnings, extracted via nothing (counted in validation).

**Tests:** fixwiki index → groups match `expected.json` stream layout; title
containing colons; missing id surfaced; empty selection → empty plan.

**DoD:** global DoD.

---

## P4.3 Multistream selective extraction
**Depends:** P4.2, P4.1.

**Deliverables** — `extraction/multistream.py`:
- Implement `WikimediaXmlDumpAdapter.extract_selected_pages` for multistream:
  for each `StreamGroup`: `seek(offset)`, read `next_offset - offset` bytes
  (or to EOF), `bz2.decompress`, wrap bytes in a synthetic root
  (`b"<root>" + data + b"</root>"`) and `iterparse` for `<page>` elements
  (namespace-agnostic tag matching); for each page parse ns, id, title,
  redirect target, latest revision id + `<text>`; yield `RawPage` only when
  `page_id ∈ group.page_ids` — **match by page ID, never title alone**
  (design §13.1). Clear elements after use (`elem.clear()`).
- Checkpoint per stream group: payload
  `{"kind":"multistream","completed_offsets":[...], "emitted": n}`. Resume:
  skip groups whose offset is in `completed_offsets`.
- Cancellation: cooperative `threading.Event` checked between groups; on
  cancel, job → `CANCELLED` with checkpoint retained.

**Tests:** extract fixture selection → exact page set + wikitext matches XML
source; resume mid-plan (kill after group 2, rerun, no duplicates — assert
via emitted page_id multiset); cancelled job resumable; corrupted stream →
EXTRACTION_PARSE_FAILED naming the offset.

**DoD:** global DoD.

---

## P4.4 Sequential fallback extraction
**Depends:** P4.3.

**Deliverables** — `extraction/sequential.py`:
- Single streaming pass of `pages-articles.xml.bz2` via `bz2.BZ2File` +
  `iterparse` (design §13.2, no full decompression to disk); yield selected
  `RawPage`s; early-exit when all selected ids have been emitted.
- Checkpoint every 1 000 pages: `{"kind":"sequential","last_page_id_seen":…,
  "emitted_ids_hash":…}`; resume skips until past `last_page_id_seen`
  (document ordering assumption: dump page order is ascending by page_id —
  verify on fixture; if violated in the wild, resume falls back to re-run with
  dedup by emitted-set stored in checkpoint).
- Adapter dispatch: `extract_selected_pages` chooses multistream when
  index present, else sequential; `enumerate_pages` (all pages) implemented
  here too (used by nothing in MVP builds but required by the P1.1 interface;
  keep trivial).

**Tests:** same selection through sequential path equals multistream path
result (byte-identical wikitext); resume correctness; early exit (reader
stops before EOF — assert via instrumented file object).

**DoD:** global DoD.

---

## P4.5 Canonical corpus writer + validation + build report
**Depends:** P4.3, P4.4, P2.4.

**Deliverables**
- `extraction/build.py` — `run_build(project_dir, lock_path, output_dir,
  events, cancel) -> BuildReport`:
  1. `verify_lock` (P2.5) against current source fingerprint — mismatch →
     fail before touching anything.
  2. Recreate manifest records from lock deterministically (P2.4) — build
     never re-decides selection.
  3. Disk-safety preflight (design §30): free space on output volume ≥
     `EST_BYTES_PER_ARTICLE × count × 1.5` + 500 MiB staging headroom, else
     `OUTPUT_DISK_INSUFFICIENT` (expert override flag `--allow-low-disk`
     permitted — integrity checks are never overridable).
  4. Extract → for each RawPage build `CorpusRecord` (categories from
     MetadataIndex; content_hash = sha256 of wikitext; document_id per P0.3),
     stream-write to **staging dir** `output_dir/.staging-<job_id>/` as
     `corpus.jsonl.zst` (zstd level 10, flushed per checkpoint) and enrich
     manifest records (revision_id, content_hash, document_id).
  5. Write `manifest.jsonl.zst`, copy `domain.yaml`, `domain.lock.json`,
     write `project.yaml` snapshot + `attribution.json` (per-record source
     licensing fields, design §25; full ATTRIBUTION.md arrives in P5.3).
  6. Atomic promote: `os.replace` staging dir → `output_dir/corpus/` only
     after validation passes (design §23).
- `validation/validate.py` — `validate_corpus(corpus_dir, lock) ->
  ValidationResult`: manifest count == corpus record count (± documented
  redirect policy); every corpus document_id in manifest and vice versa;
  corpus file re-opens and last record parses; spot-check N=25 random
  (seeded) records against manifest content_hash; required metadata fields
  present. Any failure → `VALIDATION_FAILED` detail list.
- `extraction/report.py` — assemble `BuildReport` (design §26) from
  traversal stats + extraction counters + validation result;
  `purge_eligible = validation PASSED ∧ fingerprint match`; write
  `corpus/build-report.json` and append summary to `project_dir/reports/`.

**Tests:** end-to-end fixwiki build → validate → report golden values; staging
dir cleaned on failure, output absent; validation catches an injected
mismatch (truncate corpus file); disk preflight triggers with mocked
`shutil.disk_usage`.

**DoD:** global DoD.

---

## P4.6 CLI: `build`, `validate` + resume
**Depends:** P4.5.

**Deliverables** — `cli/build_cmds.py`:
- `corpussieve build --domain LOCKPATH --project-dir DIR --output DIR2
  [--resume] [--json] [--allow-low-disk]` — runs P4.5 with Rich multi-stage
  progress (stages: verify, plan, extract, write, validate, promote); on
  existing interrupted job: without `--resume` exit 2 telling the user to pass
  `--resume` or cancel; with it, continue from checkpoint. Ctrl-C →
  cooperative cancel, state CANCELLED, exit 130.
- `corpussieve validate --corpus DIR [--json]` — standalone re-validation of
  a promoted corpus (used by purge preflight).
- State transitions: PREVIEWED→BUILDING→BUILD_SUCCEEDED→VALIDATING→VALIDATED.

**Tests:** CliRunner full build on fixwiki; interrupt/resume; `validate`
against tampered corpus exits 2 with VALIDATION_FAILED.

**DoD**
```bash
cd engine && uv run corpussieve build --domain /tmp/fixproj/domains/video-games.lock.json --project-dir /tmp/fixproj --output /tmp/fixcorpus --json
```
```bash
cd engine && uv run corpussieve validate --corpus /tmp/fixcorpus/corpus --json
```
Plus global DoD. **Phase gate:** design acceptance criteria 12, 14, 15 now
demonstrably true on fixtures; record in PROGRESS.md.
