# CorpusSieve v0.1 — User Acceptance Test Plan

Everything in `plan/PROGRESS.md` (P0–P7.4) is done and `docs/ACCEPTANCE_V0_1.md`
is 20/20 PASSED on automated evidence. This is the manual pass: you actually
touching the app and the CLI, on your own machine, before calling v0.1 real.

Report anything unexpected the same way this project already tracks issues:
add a numbered entry to `qa/FINDINGS.md` (see existing entries for the
format — what you saw, repro steps, suspected cause if any). Don't fix it
yourself unless you want to; flagging it accurately is the useful part.

---

## 0. Before you start

- Pull latest `master` (the branch was renamed from `main` this session —
  see §5 below if your local clone still has `main`).
- Nothing needs installing to *test the installer path* (§2) — that's the
  point. Building from source (§1, §3) needs the usual `uv`/`pnpm`/Rust
  toolchain per the README's Developer Setup section.

---

## 1. CLI path (the "expert" persona — acceptance criterion 2)

This exercises the same flow `qa/smoke_real_dump.sh` automates, by hand, so
you see the actual output at each step instead of a pass/fail summary.

```bash
# ~470 MB, one-time download, resumable
./qa/fetch_dumps.sh simplewiki

cd engine
uv run corpussieve source inspect --source ../dumps/simplewiki
uv run corpussieve metadata build --source ../dumps/simplewiki --project-dir ../dumps/qa_project
uv run corpussieve domain compile --domain ../examples/domains/video-games.yaml --project-dir ../dumps/qa_project
uv run corpussieve domain preview --domain ../dumps/qa_project/domain.yaml --project-dir ../dumps/qa_project
uv run corpussieve build run --domain ../dumps/qa_project/domain.lock.json --project-dir ../dumps/qa_project --output ../dumps/qa_output
uv run corpussieve validate run --corpus ../dumps/qa_output/corpus
uv run corpussieve export markdown --corpus ../dumps/qa_output/corpus --output ../dumps/qa_exports
```

**What to check:**
- [ ] `domain preview` shows a sensible article count and lets you see *why*
  a handful of pages were selected (criterion 9) — spot-check a couple you'd
  expect (e.g. a well-known game) and a couple you wouldn't.
- [ ] `validate run` reports PASSED, not just "ran without crashing."
- [ ] Open 5–10 files in `dumps/qa_exports/` at random. This is the direct
  check for Finding #9 (fixed this session): confirm you do **not** see
  leaked template markup — bare words like "Italic title" sitting alone in
  a paragraph, or run-on garbage like `developerublArikaMatrixSoftware...`
  with no spaces. A clean `**Facts**` bullet list under an infobox-derived
  article, or its clean absence with no visible warning text in the body,
  are both fine — the article prose itself should always read normally.
- [ ] Every exported file has YAML frontmatter (`title`, `page_id`,
  `license`, etc.) and the export directory has `ATTRIBUTION.md` +
  `attribution.json` (criterion 18).
- [ ] Run it all a second time from scratch — output should be byte-for-byte
  identical (design's determinism guarantee). Not required to diff by hand;
  a re-run just shouldn't fail or hang.

---

## 2. Desktop app — the real installer (the "novice" persona — criteria 1, 20)

This is the path a real user takes, unsigned-build warning included.

1. Go to the repo's **Releases** page. `v0.1.0-rc5` is currently a **draft**
   (visible to you as the repo owner, not the public) — download the
   installer for your OS from there:
   - macOS: `CorpusSieve_0.1.0_aarch64.dmg`
   - Windows: `CorpusSieve_0.1.0_x64-setup.exe` or `..._x64_en-US.msi`
   - Linux: `CorpusSieve_0.1.0_amd64.AppImage` or `..._amd64.deb`
2. Install/run it. **Expect the OS warning** described in the README's new
   "Installing the Desktop App" section:
   - [ ] macOS: Gatekeeper blocks it; right-click → Open → confirm gets you
     in. Confirm the wording roughly matches what the README told you to
     expect — if it doesn't, the README needs correcting, not the app.
   - [ ] Windows: SmartScreen "Windows protected your PC" → More info → Run
     anyway.
   - [ ] Linux: `.AppImage` should just run (`chmod +x` first if needed);
     `.deb` installs via your package manager without a comparable warning.
3. **No terminal window should appear** at any point (criterion 1).

**Walk the wizard end-to-end:**
- [ ] Project screen → point it at the `dumps/simplewiki` you fetched in §1
  (or fetch fresh from inside the app if that flow exists).
- [ ] Source inspection screen shows real fingerprint info, not placeholders.
- [ ] Model connection screen: if you have Ollama or LM Studio running
  locally, confirm it's detected. If not, confirm you can skip AI assistance
  entirely and still proceed (the manual/no-LLM path is what's fully wired
  per `qa/FINDINGS.md` #10 — this is the one to actually test).
- [ ] Domain definition screen → define something like "video games" and
  get to a preview.
- [ ] Preview screen shows counts and sample pages, matches what CLI
  `domain preview` showed in §1 for the same domain.
- [ ] Start a build. Watch the progress bar move (not just spin/freeze).
  Cancel a build partway through and confirm it actually stops (this is the
  specific bug fixed in `qa/FINDINGS.md` under P6.6 — worth re-checking by
  hand once).
- [ ] Export markdown from the finished build. Spot-check exported files
  the same way as §1's last bullet.

---

## 3. Sanity-check the unsigned-build story you're documenting

Since you said you're not paying for a certificate, the goal here is just
confirming the docs are honest about what a user experiences, not that
signing works (it deliberately doesn't).

- [ ] README's "Installing the Desktop App" section reads clearly to you as
  someone who didn't just watch it get written.
- [ ] `docs/RELEASING.md`'s signing section matches — no lingering claim
  that a real certificate is configured anywhere.

---

## 4. Optional: purge path (destructive — read first)

`corpussieve source purge` deletes the original dump after a validated
build. This is real deletion, gated by 7 preconditions (design §16.2,
tested by `tests/safety/test_destructive_invariants.py`). There is **no
CLI dry-run flag** — the only preview-before-delete path is the desktop
app's purge screen, which is required to show source paths, total bytes,
and what's retained vs. removed *before* you can confirm (design §16.3).
If you want to test this at all, only point it at a **throwaway copy** of
a dump directory you don't mind losing, and go through the desktop app so
you see the plan first:

- [ ] Desktop purge screen shows an accurate plan (paths + sizes) before
  any deletion, and the confirm step requires typing the project name
  (`--confirm-name` in the CLI, a matching confirmation input in the app).
- [ ] After confirming, the report matches what was previewed — nothing
  extra removed, nothing planned-for-removal left behind.

If you'd rather not risk it, skip this section — it's the most thoroughly
automated-tested part of the app (7 dedicated invariant tests) and the
least in need of a manual pass.

---

## 5. Housekeeping: the branch rename

The GitHub default branch is now `master` (was `main`). Your local primary
clone likely still has a local `main` tracking the now-gone `origin/main`.
To pick up the rename cleanly:

```bash
git fetch origin
git branch -m main master
git branch -u origin/master master
```

(GitHub redirects pushes/fetches to old `main` URLs automatically, so
nothing breaks in the meantime — this is just cleanup.)

---

## What "done" looks like

If every box above is checked with no surprises, v0.1 is genuinely ready —
publish the `v0.1.0-rc5` draft release (or cut a real `v0.1.0` tag) when
you're satisfied. If anything looks wrong, it's a new numbered entry in
`qa/FINDINGS.md`, same as everything else this project has caught so far.
