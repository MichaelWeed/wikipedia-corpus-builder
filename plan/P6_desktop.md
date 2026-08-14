# Phase P6 — Desktop Application (design milestone M6)

Goal: Tauri v2 shell + React wizard driving the Python engine as a bundled
sidecar over a versioned NDJSON protocol (FR-027, FR-029; design §7.1, §17,
§19). No terminal window ever appears; the engine is launched as a child
process by Tauri, not through a shell.

UI text rule: every screen's copy is drafted in `docs/UX_SPEC.md` first (that
file becomes the copy source of truth); components render those strings from
`apps/desktop/src/copy.ts`. Accessibility (design §28): all controls
keyboard-reachable, progress has text labels, no color-only status, errors
copyable.

---

## P6.1 Engine protocol v1 (spec + Python server)
**Depends:** P4.6 (and P5.4 for export methods; P3.4 for model methods).

**Deliverables**
- `docs/ENGINE_PROTOCOL.md` — normative spec: NDJSON JSON-RPC 2.0 over
  stdin/stdout; UTF-8, one JSON object per line; requests
  `{jsonrpc:"2.0", id, method, params}`; responses result/error (error.data
  carries `{code: ErrorCode, detail}`); server-initiated notifications
  `{jsonrpc:"2.0", method:"event/progress", params: ProgressEvent}` and
  `event/log`. Handshake: client calls `engine.hello {client_version}` →
  `{protocol_version: 1, engine_version}`; version mismatch → client refuses.
  Method surface (frozen; maps 1:1 onto existing internals — **no business
  logic in the API layer**):
  `engine.hello`, `project.create/open/get`, `source.inspect`,
  `metadata.build`, `model.detect/add/list/test`,
  `domain.create/proposeFacets/boundaryQuestions/applyAnswers/compile/
  resolveReviews/preview/explain`,
  `build.start/resume/cancel/status`, `corpus.validate`,
  `export.markdown/jsonl`, `purge.plan/confirm` (implemented P7),
  `job.subscribe` (enables progress events for a job).
  Long operations run in a worker thread; `id`-carrying cancel via
  `build.cancel`.
- `api/server.py` — `serve_stdio()` dispatching to the same functions the CLI
  uses (`cli/_runner` refactored so CLI and API share one service layer
  `corpussieve/service.py`; CLI keeps identical behavior — rerun P1–P5 CLI
  tests unchanged). Entry: `corpussieve engine serve` (hidden command).
- Schema export: request/response Pydantic models in `contracts/protocol.py`
  → `schemas/engine-protocol.schema.json`.

**Tests:** protocol round-trip over subprocess pipes (spawn real
`corpussieve engine serve`, drive hello → inspect → compile → build on
fixwiki, assert progress notifications arrive); malformed frame → JSON-RPC
error, process survives.

**DoD:** global DoD + subprocess protocol test green.

---

## P6.2 Tauri scaffold + sidecar wiring
**Depends:** P6.1.

**Deliverables**
- `apps/desktop/` — Tauri v2 + React 18 + TS strict + Vite + pnpm + vitest +
  eslint; `src-tauri/tauri.conf.json` with `externalBin` sidecar
  `binaries/corpussieve-engine` (per-target triple), capabilities minimal
  (no shell-open of arbitrary URLs; fs scope limited to user-chosen dirs via
  dialog plugin), window title "CorpusSieve".
- Rust: `src-tauri/src/engine.rs` — spawn sidecar (Command::sidecar) on app
  start, restart-on-crash (max 3, then error screen), pipe NDJSON;
  a thin Tauri command layer `engine_call(method, params) -> Result<Value>`
  forwarding to the child + event forwarding of `event/*` notifications to
  the webview via Tauri events.
- TS: `src/engine/client.ts` — typed client generated **manually** from
  `schemas/engine-protocol.schema.json` (one interface per method; a unit test
  asserts the method-name list matches the schema file to prevent drift).
- Dev mode: `pnpm tauri dev` uses `uv run corpussieve engine serve` via a
  `.env`-configured dev path instead of the packaged sidecar.
- PyInstaller build script `engine/scripts/build_sidecar.py` producing
  onedir bundle; CI wiring deferred to P7.4 — local build documented in
  `docs/DEV.md`. Windowed/no-console flags set (no visible terminal,
  acceptance criterion 1); engine logs to
  `platformdirs.user_log_dir("corpussieve")/engine.log`.

**DoD**
```bash
pnpm -C apps/desktop install && pnpm -C apps/desktop lint && pnpm -C apps/desktop test && pnpm -C apps/desktop build
```
Plus: `pnpm tauri dev` manually verified to reach a "hello, engine vX"
status screen (record in PROGRESS.md).

---

## P6.3 Wizard: project + source screens
**Depends:** P6.2.

**Deliverables** — wizard framework + steps 1–2 of design §7.1:
- `src/wizard/` — step router (zustand store `wizardStore`: project dir,
  inspection, provider, domain draft, lock, preview, build job), persistent
  across app restart via `project.open`.
- **Create Project** screen: name, working directory picker (Tauri dialog).
- **Choose Source** screen: file/dir picker → `source.inspect` → render dump
  kind, language/date, companion table with ✓/– and per-missing-file
  guidance text; warnings panel; "Build metadata index" action →
  `metadata.build` with progress; blocks Next until METADATA_READY.
  (Missing-metadata auto-download is post-MVP per design §7.1 — show static
  instructions with the official dumps URL instead.)

**Tests (vitest + mocked engine client):** store transitions; inspect
rendering for multistream/sequential/missing-companion fixtures (JSON
fixtures copied from engine test outputs).

**DoD:** frontend global DoD.

---

## P6.4 Wizard: model connect screens
**Depends:** P6.2 (engine P3 methods).

**Deliverables** — step 3 of design §7.1:
- Auto-probe on entry (`model.detect`); found → model table (provider, name,
  loaded badge, context length, capability status) with "Test model" per row;
  none found → provider-specific setup instructions (static copy) + manual
  URL entry with failure-class-specific messages (unreachable / auth failed /
  endpoint mismatch / no models); token input renders only after auth
  failure and is sent to engine once, never stored in frontend state
  (engine keyring handles persistence).
- Non-loopback URL → privacy note interstitial (design §8.4/§24) requiring
  explicit "I understand" before saving; toggle "don't send article samples"
  stored in provider config.
- **Skip button** is prominent: entire step optional (FR-007 manual path).

**Tests:** each failure class renders its message; skip path sets
`provider=null` and wizard continues; privacy interstitial gate.

**DoD:** frontend global DoD.

---

## P6.5 Wizard: domain define/clarify/resolve/preview screens
**Depends:** P6.3, P6.4.

**Deliverables** — steps 4–7 of design §7.1:
- **Describe Domain**: intent textarea; with provider → `domain.proposeFacets`
  spinner → editable facet chips (include/exclude); without provider →
  facet editor starts empty with guidance.
- **Clarify Boundaries**: `domain.boundaryQuestions` list, each with options +
  recommended default preselected; "Accept all recommended" button;
  `domain.applyAnswers`.
- **Resolve Domain**: root query rows → live `metadata.search` candidates with
  member counts; exact-resolved roots badge; per-root max_depth stepper
  (default 6); exclusions editor; "Compile" → `domain.compile` progress;
  review-needed categories rendered as an accept/reject queue
  (`domain.resolveReviews`).
- **Preview**: counts, size estimate, per-root/per-depth bar (plain HTML/CSS
  bars), included + borderline sample lists, contamination groups, warnings;
  "Why included?" search box → `domain.explain` rendering the provenance
  chain; too-broad/incomplete warnings block Next until acknowledged
  (checkbox, recorded into `warnings_acknowledged` on the lock via recompile).

**Tests:** facet editing round-trip; compile-with-reviews queue flow; explain
rendering; acknowledgment gating.

**DoD:** frontend global DoD.

---

## P6.6 Build/validate/export screens + progress + log viewer
**Depends:** P6.5.

**Deliverables** — steps 8–11 of design §7.1:
- **Build Mode** screen: two cards — "Extract and keep source" (default) /
  "Extract, verify, then purge source" (advanced, shows the §16.1
  explanation that compressed dumps can't be edited in place; selecting it
  only sets a flag consumed by P7.2's cleanup step).
- **Build** screen: stage list (verify/plan/extract/write/validate/promote)
  with per-stage progress from `event/progress`; pause N/A (not in engine
  contract) but **Cancel** → `build.cancel` → resumable state banner with
  Resume button (`build.resume`).
- **Validate/Report** screen: renders `build-report.json` (design §26
  dashboard) — counts, samples, warnings, validation badge, purge
  eligibility.
- **Export** screen: markdown/jsonl toggles → `export.*`; "Open output
  folder" (Tauri opener, scoped); AnythingLLM guide link.
- **Log viewer**: tail of `event/log` ring buffer (5 000 lines), copy-all
  button; expert mode toggle in settings reveals raw error detail
  (design §29).

**Tests:** progress event reduction into stage states; cancel/resume flow
against scripted mock; report rendering golden snapshot.

**DoD:** frontend global DoD.

---

## P6.7 Desktop E2E tests (mocked engine)
**Depends:** P6.6.

**Deliverables**
- `apps/desktop/e2e/` — WebdriverIO + tauri-driver (Linux CI) happy-path E2E:
  scripted mock engine binary (`e2e/mock-engine.py` speaking protocol v1 from
  recorded fixture responses) driving: first-run → project → source →
  skip-model → manual domain → compile → preview acknowledge → build →
  report → export (design §32 Desktop E2E list; purge E2E added in P7.3).
  Error-recovery scenario: engine crash mid-build → restart banner → resume.
- CI job added to `desktop.yml` (Linux only for E2E; unit tests all 3 OS).

**DoD:** E2E suite green locally and in CI; frontend + engine global DoD.
**Phase gate:** acceptance criteria 1 (no terminal), 5, 9 verified manually on
at least one OS; record results in PROGRESS.md.
