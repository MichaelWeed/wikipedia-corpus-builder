# CorpusSieve v0.1 Acceptance Matrix

Restored to Design §38 ("38. Key Acceptance Criteria for v0.1"). All 20 design acceptance criteria are mapped to executable automated test IDs, CI workflows, or manual runbook steps.

| ID | Acceptance Criterion (Design §38) | Verification Method | Status | Date |
|---|---|---|---|---|
| 1 | A novice can install and launch the desktop app without seeing a terminal window | Manual: `pnpm tauri build --debug` bundle, launched via `open` (macOS double-click path)[^1] | PASSED | 2026-08-14 |
| 2 | An expert can complete the same core workflow from CLI | `tests/cli/` suite + manual simplewiki runbook | PASSED | 2026-08-13 |
| 3 | An existing Wikimedia dump can be inspected without full decompression | `tests/sources/test_fingerprint.py` + real 31 GB enwiki 20260801 inspected in 0.21 s | PASSED | 2026-08-14 |
| 4 | A local Ollama or LM Studio server can be detected through API | `tests/models/test_ollama.py` | PASSED | 2026-08-13 |
| 5 | Available and loaded/running models are visible to the user | `tests/models/test_ollama.py` | PASSED | 2026-08-13 |
| 6 | "Keep things related to video games" can become a user-reviewed domain definition | `tests/domain/test_traverse.py` + `test_select.py` | PASSED | 2026-08-13 |
| 7 | All selected roots are verified against the local source metadata | `tests/domain/test_lock_build.py` | PASSED | 2026-08-13 |
| 8 | Category traversal cannot loop indefinitely | `tests/domain/test_traverse.py` (cycle protection) | PASSED | 2026-08-13 |
| 9 | The user can preview and inspect why pages are selected | `tests/domain/test_preview.py` | PASSED | 2026-08-13 |
| 10 | A resolved lock is produced before build | `tests/domain/test_lock_build.py` | PASSED | 2026-08-13 |
| 11 | The build consumes the lock and does not ask the LLM to improvise new rules | `tests/extraction/test_build.py` | PASSED | 2026-08-13 |
| 12 | The selected corpus can be extracted from a real multistream dump | `tests/extraction/test_multistream.py` (synthetic fixture only) | FAILED | 2026-08-14 |
| 13 | Canonical JSONL and Markdown exports are produced | `tests/exporters/` + `tests/cli/test_export_cli.py` | PASSED | 2026-08-13 |
| 14 | The build can resume after interruption | `tests/extraction/test_build_resume_bugs.py` + `tests/jobs/test_state.py` | PASSED | 2026-08-14 |
| 15 | The original source remains unchanged after ordinary build | `tests/safety/test_destructive_invariants.py::test_build_never_deletes_source` | PASSED | 2026-08-14 |
| 16 | Source purge cannot occur after a failed validation or changed source | `tests/safety/test_destructive_invariants.py` (4 blocking tests) | PASSED | 2026-08-14 |
| 17 | A successful purge clearly reports what was removed and what was retained | `tests/safety/test_destructive_invariants.py::test_purge_removes_only_planned_files` | PASSED | 2026-08-14 |
| 18 | Every exported article carries source/attribution metadata | `tests/cli/test_export_cli.py` | PASSED | 2026-08-13 |
| 19 | CI passes on macOS, Windows, and Linux | Remote CI runner execution | NOT_RUN | - |
| 20 | A clean machine does not need Python/Node/Rust installed to run the desktop release | Packaged sidecar install test | FAILED | - |

[^1]: Verified on macOS (aarch64) only: `cargo check`/`cargo build` pass, `pnpm tauri build --debug` produces `CorpusSieve.app` and a `.dmg`, and the `.app` was launched via `open` (the real double-click path) with no terminal window and no crash. This is a local **debug** build a developer produced, not a signed/notarized installer a novice would download — that remains P7.4. It also still shells out to `uv run corpussieve engine serve` at runtime (see criterion 20), so it requires Python/uv on the machine; the bundled-sidecar (`externalBin`) packaging that removes that dependency is still open in P6.2.

## Smoke Test Runbook (`simplewiki`)

> **Status 2026-08-14:** this runbook cannot complete past step 2. Building the
> metadata index from a current dump yields **zero** category edges and
> memberships — MediaWiki replaced `categorylinks.cl_to` with `cl_target_id`
> → `linktarget`, and the parser still reads the retired schema. See
> `qa/FINDINGS.md` #1. Criterion 12 therefore remains **unverified against real
> data**. Use `./qa/smoke_real_dump.sh`, which halts with a clear diagnostic.

To run an end-to-end smoke test on a small real-world Wikimedia dump (`simplewiki`):

1. Download the dump set:
   ```bash
   ./qa/fetch_dumps.sh simplewiki
   ```
   This fetches five files (including `linktarget.sql.gz`, required by current
   dumps) using **dated** filenames. Do **not** use the `-latest-` filenames
   from `dumps.wikimedia.org/<wiki>/latest/`: `parse_dump_filename` requires a
   `YYYYMMDD` date and rejects them with `SOURCE_UNSUPPORTED`, and a moving
   "latest" would break the source-fingerprint reproducibility guarantee
   (design §9.3).
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
