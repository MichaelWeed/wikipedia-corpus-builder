# Phase P7 — Safe Purge & Release Hardening (design milestone M7)

Goal: the only destructive feature in the product, implemented last, behind
every gate the design demands (FR-026; design §16), plus release packaging and
the v0.1 acceptance run. `safety/` is the only package permitted to delete or
move source files — enforce with a lint rule (ruff `flake8-tidy-imports`
banning `os.remove/os.unlink/shutil.rmtree/send2trash` outside
`corpussieve/safety/` and test code; add `send2trash>=1.8` as the one new
dependency, sanctioned here).

---

## P7.1 Purge preconditions + executor
**Depends:** P4.6.

**Deliverables**
- `safety/preconditions.py` — `check_purge_preconditions(project_dir) ->
  PurgePlan | list[PurgeBlocker]`. ALL of design §16.2, each its own named
  check returning a typed blocker:
  1. build state == VALIDATED (or EXPORTED) — else `PURGE_OUTPUT_UNVERIFIED`;
  2. validation status PASSED in build-report — else `PURGE_OUTPUT_UNVERIFIED`;
  3. **re-fingerprint source now**; must equal build fingerprint — else
     `PURGE_SOURCE_CHANGED`;
  4. canonical corpus opens and validates (`validate_corpus` re-run);
  5. manifest count == corpus count;
  6. every delete target resolved via `Path.resolve()` (symlinks
     canonicalized); output dir must not be inside any delete target and no
     delete target inside output — else blocker `output_inside_target`;
  7. purge was explicitly requested (flag/param, never inferred).
  `PurgePlan`: files (path, bytes), total_bytes, reversible (trash
  available?), corpus_path, report summary.
- `safety/purge.py` — `execute_purge(plan, mode: Literal["trash",
  "permanent"], confirm_token: str) -> PurgeResult`:
  re-runs preconditions immediately before deletion (TOCTOU window
  minimized); `trash` via `send2trash`; `permanent` via unlink;
  `confirm_token` must equal the project name (design §16.3 typed
  confirmation — validated here in the engine, not only in UI). Deletes ONLY
  files listed in the plan. `PurgeResult`: removed (paths+bytes), retained
  corpus path, written to `reports/purge-<ts>.json` and job state →
  SOURCE_PURGED. **No flag may bypass a blocker — there is deliberately no
  force parameter in these signatures** (design §16.4).

**Tests:** every blocker triggers on a doctored fixture project (7 cases);
symlink pointing source→output detected; happy path removes exactly the
planned files and nothing else (assert directory diff); wrong confirm_token
rejected; TOCTOU (source modified between plan and execute) blocked.

**DoD:** global DoD; ruff ban rule active and passing.

---

## P7.2 Purge UX (CLI + desktop confirmations)
**Depends:** P7.1, P6.6.

**Deliverables**
- `cli/source_cmds.py::purge` — `corpussieve source purge --project DIR
  [--json]`: renders plan (files, sizes, reversibility, corpus path,
  §16.3 warning about re-downloading); interactive: type project name to
  confirm; then trash/permanent choice with a second, stronger confirmation
  for permanent ("Trash may not free space" note per design §7.1 step 12).
  Non-interactive automation: requires `--i-understand-this-deletes-the-source`
  AND `--confirm-name NAME` AND `--mode trash|permanent`; all engine
  preconditions still enforced (design §16.4).
- Engine protocol: implement `purge.plan` / `purge.confirm {mode,
  confirm_token}` (spec'd in P6.1).
- Desktop **Cleanup** step (design §7.1 step 12): only reachable when the
  P6.6 "purge" build mode flag is set AND report says purge_eligible; shows
  the §16.3 checklist; typed-name confirmation field; separate
  permanent-delete confirmation dialog; success screen shows PurgeResult
  (what was removed / retained — acceptance criterion 17).

**Tests:** CliRunner interactive (scripted stdin) + non-interactive flag
matrix (each missing flag → refusal); desktop component tests for both
confirmation gates.

**DoD:** global + frontend DoD.

---

## P7.3 Destructive-safety test suite
**Depends:** P7.2.

**Deliverables** — `engine/tests/safety/test_destructive_invariants.py`, the
design §32 "Destructive safety" list as named tests (these are the release
blockers):
- `test_build_never_deletes_source` — full build on a tmp copy; assert
  source tree byte-identical before/after (hash walk).
- `test_failed_validation_blocks_purge`
- `test_changed_source_blocks_purge`
- `test_output_inside_delete_target_blocks_purge`
- `test_symlink_canonicalization_cannot_escape_scope` — hostile symlinks and
  `..` segments in project.yaml paths cannot make the plan reach outside the
  source directory.
- `test_purge_removes_only_planned_files`
- Plus desktop E2E purge scenario appended to P6.7 suite (mock engine
  asserting typed confirmation reached the `purge.confirm` call).
- CI: these tests get their own required job (`safety` matrix on 3 OS,
  including a Windows path-semantics run).

**DoD:** suite green on all 3 OS in CI; global DoD.

---

## P7.4 Release engineering + v0.1 acceptance run
**Depends:** P7.3, P6.7, P5.4.

**Deliverables**
- `.github/workflows/release.yml` (tag-triggered `v*`): 3-OS matrix —
  build PyInstaller sidecars, `tauri build` installers (macOS .dmg, Windows
  .msi/NSIS, Linux AppImage + .deb), CLI sdist/wheel to artifact, SHA-256
  `checksums.txt`, SBOM (CycloneDX via `uv export` + `cargo cyclonedx` +
  `pnpm licenses`), draft GitHub release with generated notes template.
- Signing (design §33): workflow consumes secrets
  (`APPLE_CERT/APPLE_ID/NOTARY_*`, `WINDOWS_CERT_*`) **when present**, and
  degrades to unsigned artifacts with a loud warning otherwise — pipeline
  must be runnable without secrets; signing docs in `docs/RELEASING.md`
  (exact steps to provision certs; secrets live only in CI storage).
- `docs/RELEASING.md` also defines the version bump + changelog process and
  the supported-platform matrix (design §34).
- **v0.1 acceptance checklist run**: `docs/ACCEPTANCE_V0_1.md` — the 20
  criteria from design §38 as a table with columns (criterion, how verified:
  automated test ID / manual step, result, date). Criteria 3–18 map to
  existing automated tests (cite test paths); 1, 2, 19, 20 are
  manual/CI-verified. The release is blocked until every row is checked.
  A real-dump smoke test (criterion 12) is documented as a manual runbook
  using `simplewiki` (smallest realistic dump) — command sequence given in
  the doc; do not commit any real dump.

**DoD:** tag `v0.1.0-rc1` produces installers + checksums + SBOM in CI on all
3 OS; `ACCEPTANCE_V0_1.md` fully checked; PROGRESS.md marks the plan complete.
