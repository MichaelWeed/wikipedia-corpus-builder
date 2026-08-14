# CorpusSieve v0.1 Acceptance Matrix

Restored to Design §38 ("38. Key Acceptance Criteria for v0.1"). All 20 design acceptance criteria are mapped to executable automated test IDs, CI workflows, or manual runbook steps.

| ID | Acceptance Criterion (Design §38) | Verification Method | Status | Date |
|---|---|---|---|---|
| 1 | A novice can install and launch the desktop app without seeing a terminal window | Manual: `pnpm tauri build --debug` bundle, launched via `open` (macOS double-click path)[^1] | PASSED | 2026-08-14 |
| 2 | An expert can complete the same core workflow from CLI | `tests/cli/` suite + manual simplewiki runbook | PASSED | 2026-08-13 |
| 3 | An existing Wikimedia dump can be inspected without full decompression | `tests/sources/test_fingerprint.py` + real 31 GB enwiki 20260801 inspected in 0.21 s | PASSED | 2026-08-14 |
| 4 | A local Ollama or LM Studio server can be detected through API | `tests/models/test_ollama.py` | PASSED | 2026-08-13 |
| 5 | Available and loaded/running models are visible to the user | `tests/models/test_ollama.py` | PASSED | 2026-08-13 |
| 6 | "Keep things related to video games" can become a user-reviewed domain definition | `tests/domain/test_traverse.py` + `test_select.py`; real-data: 3,372 articles selected from simplewiki via `Category:Video_games` (751 categories traversed) | PASSED | 2026-08-14 |
| 7 | All selected roots are verified against the local source metadata | `tests/domain/test_lock_build.py`; real-data root resolution confirmed on simplewiki | PASSED | 2026-08-14 |
| 8 | Category traversal cannot loop indefinitely | `tests/domain/test_traverse.py` (cycle protection) | PASSED | 2026-08-13 |
| 9 | The user can preview and inspect why pages are selected | `tests/domain/test_preview.py`; real-data preview verified (counts by root/depth, samples, warnings) on simplewiki | PASSED | 2026-08-14 |
| 10 | A resolved lock is produced before build | `tests/domain/test_lock_build.py` | PASSED | 2026-08-13 |
| 11 | The build consumes the lock and does not ask the LLM to improvise new rules | `tests/extraction/test_build.py` | PASSED | 2026-08-13 |
| 12 | The selected corpus can be extracted from a real multistream dump | `tests/extraction/test_multistream.py` + real end-to-end: 3,372 real "video games" articles built and validated from simplewiki 20260801 (FINDINGS #1 fixed) | PASSED | 2026-08-14 |
| 13 | Canonical JSONL and Markdown exports are produced | `tests/exporters/` + `tests/cli/test_export_cli.py`; real-data: 3,372 markdown files exported from simplewiki (output quality issue tracked separately, FINDINGS #9) | PASSED | 2026-08-14 |
| 14 | The build can resume after interruption | `tests/extraction/test_build_resume_bugs.py` + `tests/jobs/test_state.py` | PASSED | 2026-08-14 |
| 15 | The original source remains unchanged after ordinary build | `tests/safety/test_destructive_invariants.py::test_build_never_deletes_source` | PASSED | 2026-08-14 |
| 16 | Source purge cannot occur after a failed validation or changed source | `tests/safety/test_destructive_invariants.py` (4 blocking tests) | PASSED | 2026-08-14 |
| 17 | A successful purge clearly reports what was removed and what was retained | `tests/safety/test_destructive_invariants.py::test_purge_removes_only_planned_files` | PASSED | 2026-08-14 |
| 18 | Every exported article carries source/attribution metadata | `tests/cli/test_export_cli.py` | PASSED | 2026-08-13 |
| 19 | CI passes on macOS, Windows, and Linux | `engine.yml` + `desktop.yml`, GitHub Actions runs [31845502972](https://github.com/MichaelWeed/wikipedia-corpus-builder/actions/runs/31845502972) / [31845502955](https://github.com/MichaelWeed/wikipedia-corpus-builder/actions/runs/31845502955)[^3] | PASSED | 2026-08-14 |
| 20 | A clean machine does not need Python/Node/Rust installed to run the desktop release | `apps/desktop/src-tauri/src/engine.rs::tests::spawns_bundled_sidecar_and_completes_a_real_rpc_round_trip`[^2] | PASSED | 2026-08-14 |

[^1]: Verified on macOS (aarch64) only: `cargo check`/`cargo build` pass, `pnpm tauri build --debug` produces `CorpusSieve.app` and a `.dmg`, and the `.app` was launched via `open` (the real double-click path) with no terminal window and no crash. This is a local **debug** build a developer produced, not a signed/notarized installer a novice would download — that remains P7.4/signing (see `docs/RELEASING.md`, unverified without real certificates).

[^2]: Verified on macOS (aarch64) only, 2026-08-14 (P6.2): `engine/scripts/build_sidecar.sh` freezes the engine into a standalone PyInstaller executable; `engine.rs::spawn_sidecar()` spawns it directly (no `uv run` in the packaged path); the Rust test copies the real built binary next to the test executable — exactly where Tauri's bundler places it in a real `.app`, confirmed by inspecting an actual `tauri build --debug` output — and drives a genuine `engine.hello` JSON-RPC round trip through it. Independently confirmed manually: `env -i PATH=/usr/bin:/bin ... corpussieve-engine engine serve` answered real RPC calls (`engine.hello`, `source.inspect`) with no `uv`/Python anywhere on `PATH`. Not yet verified: Windows/Linux (target-triple naming and `.exe` handling are implemented per Tauri's documented convention but untested), and this is still an unsigned/non-notarized local build (see criterion 1's footnote and `docs/RELEASING.md`).

[^3]: `engine.yml` and `desktop.yml` are genuinely green on all 6 matrix legs (ubuntu/macos/windows × the two workflows) as of 2026-08-14, verified by actually pushing and watching GitHub Actions run — not inferred from local testing. It took four consecutive pushes to get there, each surfacing a real, previously-latent bug that "verified locally" had never caught (all recorded in `qa/FINDINGS.md` #11–14): `test_cli_export_markdown_and_jsonl` depended on an ambient fixture no test generates or commits; the Linux system-dependency list had two conflicting packages; nothing built `apps/desktop/dist/` before the bare `cargo check`/`cargo test` steps needed it; a purge-safety test picked a file to tamper via directory-iteration order, which is alphabetical on Windows (NTFS) but not on macOS/Linux, so it silently tampered the wrong file there; gzip-compressed fixture regeneration isn't byte-identical across zlib versions/platforms; and a new Rust test's own Windows cleanup raced a file lock the OS holds briefly after killing a process. This criterion covers the **regular CI matrix only** — `release.yml` (the tag-triggered installer/SBOM/signing pipeline, P7.4) only runs on a `v*` tag push, which has not happened; it remains unverified against real infrastructure, see `docs/RELEASING.md`.

## Smoke Test Runbook (`simplewiki`)

> **Status 2026-08-14:** this runbook now completes end-to-end. It previously
> failed at step 2 (`qa/FINDINGS.md` #1, fixed same day) because current
> Wikimedia dumps replaced `categorylinks.cl_to` with `cl_target_id` →
> `linktarget`. `./qa/smoke_real_dump.sh` runs this full sequence and confirms
> real category data, real selection, and a real extracted/validated corpus —
> it last completed with 3,372 real articles from simplewiki.

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
