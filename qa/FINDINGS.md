# CorpusSieve — QA & Security Findings

**Date:** 2026-08-14
**Scope:** full codebase (no remote configured, so `/security-review`'s
`git diff origin/HEAD...` was unavailable; reviewed the whole tree instead)
plus first-ever execution against a **real Wikimedia dump** (simplewiki 20260801).

Findings are ordered by severity. Each was **empirically reproduced**, not
inferred from reading code.

---

## 1. BLOCKER — CorpusSieve ingests zero category data from current Wikimedia dumps

**Impact:** The core product feature (domain compilation via category graph
traversal) is completely non-functional on real Wikipedia data. This is not a
degradation; it is total.

**Scope is limited to the metadata/category layer.** The extraction half of the
product was tested independently against the real 25 GB enwiki dump and
**works correctly**: the multistream index parsed 400,000 entries in 0.4 s, and
`extract_selected_pages({12, 25, 39})` returned Anarchism (113,647 chars),
Autism spectrum, and Albedo (71,574 chars) with correct revision IDs in 30 s,
without decompressing the full file. CorpusSieve is one schema fix away from a
working end-to-end pipeline on real Wikipedia.

**Reproduced:** built the metadata index from the real simplewiki 20260801 dump:

| table | rows |
|---|---|
| `pages` | 945,561 |
| `categories` | 92,980 (from `page.sql` namespace-14 only) |
| `category_edges` | **0** |
| `category_membership` | **0** |

**Root cause:** MediaWiki migrated the `categorylinks` schema. The real 2026
dump has **no `cl_to` column**:

```
categorylinks(cl_from, cl_sortkey, cl_timestamp, cl_sortkey_prefix,
              cl_type, cl_collation_id, cl_target_id)
```

The category *name* is no longer in `categorylinks` at all — `cl_target_id` is
a foreign key into a new `linktarget(lt_id, lt_namespace, lt_title)` table.

`engine/src/corpussieve/metadata/rows.py` reads the **old** schema:
`row[1]` as `cl_to` (actually `cl_sortkey`, binary) and `row[6]` as `cl_type`
(actually `cl_target_id`, an integer). Since `row[6]` never equals
`page`/`subcat`, **every row is silently skipped** — no error, no warning, just
an empty graph.

**Why tests never caught it:** the synthetic fixtures in
`engine/tests/fixtures/generator.py` were generated with the *old* schema, so
the entire test suite validates against a dump format Wikimedia no longer
publishes. All 116 tests pass against a format that doesn't exist in the wild.

**Fix required:**
1. Ingest `<proj>-<date>-linktarget.sql.gz` (a 5th source file — already
   downloaded to `dumps/simplewiki/` and `dumps/enwiki/`) and join
   `cl_target_id → lt_id` where `lt_namespace = 14` to recover category titles.
2. Support **both** schemas — detect which columns exist so older dumps and the
   existing fixtures keep working.
3. Add `linktarget` to `SourceAdapter.inspect()` companion detection and to the
   `SOURCE_COMPANION_MISSING` warnings.
4. Regenerate fixtures to cover the new schema, or add a second fixture set.
5. **Fail loudly**, not silently: an ingest that produces 0 edges from a
   non-empty `categorylinks` should raise `METADATA_PARSE_FAILED`.

---

## 2. HIGH (data loss) — "Move to Trash" can silently perform a permanent delete

**File:** `engine/src/corpussieve/safety/purge.py`

```python
if mode == "trash" and HAS_SEND2TRASH:
    send2trash.send2trash(str(f_path))
else:
    f_path.unlink()          # ← permanent, and reached when mode == "trash"
```

If `send2trash` is unavailable for any reason (import failure, trimmed install,
packaging omission in the future PyInstaller sidecar), a user who explicitly
chose the **reversible** option gets **irreversible destruction of their only
copy of a 25 GB dump**, with no warning and `status: "SUCCESS"`.

**Reproduced:** with `HAS_SEND2TRASH = False` and `mode="trash"`, the target
file was permanently unlinked (not recoverable from Trash).

This directly violates design §16.3, which requires Trash vs. permanent to be
distinct choices with permanent gated behind a *stronger* confirmation.

**Fix:** if `mode == "trash"` and `send2trash` is unavailable, **abort** with a
blocker. Never silently downgrade to a more destructive operation.

---

## 3. HIGH (misleading safety UI) — `PurgePlan.reversible` is hardcoded `True`

**File:** `engine/src/corpussieve/safety/preconditions.py` (plan construction)

`reversible=True` is a literal, independent of the chosen mode or whether
`send2trash` is even available. Design §16.3 requires the confirmation UI to
show "Whether deletion is reversible" — both the CLI and the desktop
`PurgeScreen` will therefore tell the user a permanent deletion is reversible.
Compounds finding #2.

**Fix:** derive it (`mode == "trash" and HAS_SEND2TRASH`).

---

## 4. MEDIUM (data loss) — Purge deletes *every* file under the source directory

**File:** `engine/src/corpussieve/safety/preconditions.py`

```python
items_to_check = list(source_dir.rglob("*")) if source_dir.is_dir() else [source_dir]
```

Every file recursively under the source directory is added to the delete plan —
not just the recognized dump files. A user who points `--source` at a shared
folder (e.g. `~/Downloads`, which is a plausible place to leave a dump) would
have *unrelated personal files* enrolled for deletion.

Mitigated by the confirmation showing the file list, but the plan should be
restricted to files the adapter actually recognized as dump components.

---

## 5. MEDIUM (DoS) — XML entity expansion reachable in the sequential extractor

**File:** `engine/src/corpussieve/extraction/sequential.py`

Uses stdlib `xml.etree.ElementTree` with no DTD hardening. Design §24 declares
dump content untrusted input.

**Reproduced** through the real parsing pattern: a 331-byte payload expanded to
100,000 characters (**302×**) at only 4 nesting levels; expansion is
exponential, so ~9 levels exhausts memory.

- **XXE / local file disclosure: NOT vulnerable** ✅ — ElementTree refuses
  external entities (`undefined entity` ParseError). Verified explicitly.
- **Multistream path: incidentally safe** ✅ — wrapping decompressed bytes in a
  synthetic `<root>` makes any `DOCTYPE` a parse error.
- **Sequential path: vulnerable** ❌ — parses raw dump bytes directly.

**Fix:** use `defusedxml` (`forbid_dtd=True`), or reject any dump whose prolog
contains a `DOCTYPE`.

**Realistic severity:** requires the user to open a maliciously crafted dump;
official dumps over HTTPS are not a practical vector. Local DoS only — no code
execution and no data exfiltration.

---

## 6. LOW — `bz2.decompress()` on an unbounded stream slice

`engine/src/corpussieve/extraction/multistream.py` decompresses a whole stream
into memory with no size ceiling. Bounded in practice by index offsets, but a
hostile dump could declare a large stream. Consider a decompression cap.

---

## 7. LOW — No explicit HTTPS→HTTP downgrade guard

Design §24 requires "do not silently downgrade HTTPS to HTTP" for model
endpoints. No such check exists in `engine/src/corpussieve/models/config.py`.

---

## 8. LOW (docs) — The documented smoke-test runbook cannot work as written

`docs/ACCEPTANCE_V0_1.md` instructs downloading `*-latest-*` files from
`dumps.wikimedia.org/<wiki>/latest/`. `parse_dump_filename` requires a
`YYYYMMDD` date, so those filenames are rejected with `SOURCE_UNSUPPORTED`.

**Confirmed:** `source inspect` on the freshly downloaded `-latest-` files
failed; renaming to `simplewiki-20260801-*` fixed it immediately.

Downloading from the **dated** directory is also more correct: "latest" is a
moving target, which would silently break the source-fingerprint reproducibility
guarantee (design §9.3). `qa/fetch_dumps.sh` handles this correctly.

---

## Clean results (verified, no action needed)

- **SQL injection:** none. Every `execute()` is parameterized; no f-string or
  concatenated SQL anywhere in `src/`.
- **XXE / local file disclosure:** blocked by ElementTree (tested explicitly).
- **Path traversal in exports:** `exporters/naming.py::slugify` is solid —
  strips `/` and `\`, collapses `..` to `untitled`, handles Windows reserved
  names, NFC-normalizes, length-caps.
- **Secret handling:** tokens go to the OS keyring, never to `providers.yaml`
  (design §21 satisfied). No TLS verification is disabled anywhere.
- **LLM trust boundary:** model output is schema-validated and never executed,
  never used as a filesystem path.
