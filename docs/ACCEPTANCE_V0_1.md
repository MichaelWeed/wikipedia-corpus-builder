# CorpusSieve v0.1 Acceptance Matrix

All 20 design acceptance criteria are mapped to executable automated test IDs or manual runbook steps.

| ID | Acceptance Criterion | Verification Method | Status | Date |
|---|---|---|---|---|
| 1 | No visible terminal window ever appears during desktop launch/operation | Manual / Tauri windowed flag | PASSED | 2026-08-13 |
| 2 | Pure offline mode: fully functional without internet access | `tests/models/test_ollama.py` (respx zero-HTTP) | PASSED | 2026-08-13 |
| 3 | Wikimedia XML dump inspection & quick-hash fingerprinting | `tests/sources/test_fingerprint.py` | PASSED | 2026-08-13 |
| 4 | Streaming SQL index build (`page`, `categorylinks`) to SQLite | `tests/metadata/test_build.py` | PASSED | 2026-08-13 |
| 5 | Category graph traversal with depth bounding and cycle protection | `tests/domain/test_traverse.py` | PASSED | 2026-08-13 |
| 6 | Article selection algorithm & compressed manifest output | `tests/domain/test_select.py` | PASSED | 2026-08-13 |
| 7 | Deterministic lockfile compiler & tamper verification | `tests/domain/test_lock_build.py` | PASSED | 2026-08-13 |
| 8 | Explanation provenance audit (`explain_page_selection`) | `tests/domain/test_preview.py` | PASSED | 2026-08-13 |
| 9 | Local LLM provider adapters (Ollama / LM Studio) | `tests/models/test_ollama.py` | PASSED | 2026-08-13 |
| 10 | Ambiguous-branch review engine with SQLite decision caching | `tests/domain/test_branch_review.py` | PASSED | 2026-08-13 |
| 11 | Multistream bz2 selective seeking extractor | `tests/extraction/test_multistream.py` | PASSED | 2026-08-13 |
| 12 | Sequential streaming fallback extractor | `tests/extraction/test_sequential.py` | PASSED | 2026-08-13 |
| 13 | Job store state machine & SQLite checkpoint recovery | `tests/jobs/test_state.py` | PASSED | 2026-08-13 |
| 14 | Atomic promoter via staging directory & `os.replace` | `tests/extraction/test_build.py` | PASSED | 2026-08-13 |
| 15 | Integrity validator with random sha256 spot check | `tests/validation/test_validate.py` | PASSED | 2026-08-13 |
| 16 | RAG-ready Wikitext to Markdown normalizer & frontmatter | `tests/normalization/test_wikitext_md.py` | PASSED | 2026-08-13 |
| 17 | Path-traversal safe filename slugifier | `tests/exporters/test_naming.py` | PASSED | 2026-08-13 |
| 18 | Human & machine attribution generators (`ATTRIBUTION.md`) | `tests/cli/test_export_cli.py` | PASSED | 2026-08-13 |
| 19 | Safe purge 7-precondition checklist & typed token verification | `tests/safety/test_destructive_invariants.py` | PASSED | 2026-08-13 |
| 20 | Subprocess NDJSON JSON-RPC stdio engine protocol server | `tests/api/test_server.py` | PASSED | 2026-08-13 |

## Smoke Test Runbook (`simplewiki`)
To run an end-to-end smoke test on a small real-world Wikimedia dump (`simplewiki`):

1. Download latest simplewiki dump files into `./dumps`:
   ```bash
   curl -O https://dumps.wikimedia.org/simplewiki/latest/simplewiki-latest-pages-articles-multistream.xml.bz2
   curl -O https://dumps.wikimedia.org/simplewiki/latest/simplewiki-latest-pages-articles-multistream-index.txt.bz2
   curl -O https://dumps.wikimedia.org/simplewiki/latest/simplewiki-latest-page.sql.gz
   curl -O https://dumps.wikimedia.org/simplewiki/latest/simplewiki-latest-categorylinks.sql.gz
   ```
2. Build metadata & compile domain:
   ```bash
   corpussieve metadata build --source ./dumps --project-dir ./my_project
   corpussieve domain compile --domain ./examples/domains/video-games.yaml --project-dir ./my_project
   ```
3. Run build and export:
   ```bash
   corpussieve build run --domain ./my_project/domain.lock.json --project-dir ./my_project --output ./my_output
   corpussieve export markdown --corpus ./my_output/corpus --output ./exports/markdown
   ```
