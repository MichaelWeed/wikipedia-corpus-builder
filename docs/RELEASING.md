# Releasing CorpusSieve

This document describes the release engineering, versioning, code signing, and release procedures for CorpusSieve.

## Supported OS Matrix
- macOS (Apple Silicon arm64 & Intel x86_64) — `.dmg` installer & standalone `.app`
- Windows 10/11 (x64) — `.msi` and/or NSIS `.exe` installer
- Linux (x86_64) — `.AppImage` & `.deb` packages

Each platform's installer bundles the engine as a standalone PyInstaller
binary (`engine/scripts/build_sidecar.sh`, P6.2) — end users do not need
Python, Node, or Rust installed.

## Version Bump & Changelog Process

1. Bump the version in both `engine/pyproject.toml` (`[project].version`)
   and `apps/desktop/src-tauri/tauri.conf.json` (`.version`) — keep them in
   sync; there is no automated cross-check for this yet.
2. Summarize notable changes since the last tag at the top of a `CHANGELOG`
   entry (this repo does not yet have a `CHANGELOG.md`; until it does, rely
   on the GitHub release's auto-generated notes from `release.yml`, which
   lists merged PRs/commits since the previous tag).
3. Commit the version bump, then follow the Release Checklist below.

## Release Checklist

1. Verify all 20 acceptance criteria in `docs/ACCEPTANCE_V0_1.md`. The
   release is blocked until every row is checked PASSED.
2. Run the full local gate suite:
   ```bash
   ./qa/run_all_gates.sh
   ```
3. Tag release:
   ```bash
   git tag -a v0.1.0-rc1 -m "CorpusSieve v0.1.0-rc1 release candidate"
   git push origin v0.1.0-rc1
   ```
4. GitHub Actions release pipeline (`.github/workflows/release.yml`) builds,
   on each of the 3 platforms:
   - the engine sidecar (PyInstaller) and desktop installer (`tauri build`),
   - the engine's Python wheel/sdist for CLI-only installs (built once, on
     Linux, since it's pure-Python — see `engine/pyproject.toml`),
   - a CycloneDX SBOM for Rust deps (`cargo-cyclonedx`) and Python deps
     (`uv export` piped through `cyclonedx-py`, built once on Linux), plus a
     `pnpm licenses list` report for Node deps (not CycloneDX — see the
     note below on why),
   - SHA-256 `checksums.txt` covering every artifact.
   It then drafts a GitHub release (`draft: true`, so nothing is published
   automatically) with all platform artifacts attached and auto-generated
   release notes. Review and publish it manually.

**Verification status of this pipeline (2026-08-15):** genuinely green on
all 3 OSes, confirmed by five real tag pushes (`v0.1.0-rc1` through `rc5`)
watched on real GitHub Actions — not inferred from local testing. `rc5`
produced a real draft GitHub release with real installer artifacts (macOS
`.dmg`, Linux `.AppImage`/`.deb`, Windows `.exe`/`.msi`), engine
wheel/sdist, all three SBOM/license files, and checksums. The first four
attempts each surfaced a real, previously-untested bug — full root-cause
analysis in `qa/FINDINGS.md` #15, #16, #18 (and #17, a wrong hypothesis
about GitHub Actions cache corruption, refuted and kept for an honest
trail). Signing remains genuinely unverified — see below — since no real
certificates have been provisioned; every build so far is
unsigned/ad-hoc-signed, exactly as this pipeline is designed to degrade.

## Code Signing Secrets

Tauri's CLI signs (and, on macOS, notarizes) automatically when these
environment variables are present, and produces an unsigned build with a
loud `::warning::` (surfaced in the workflow's job summary) when they
aren't — the pipeline is runnable without any of them. Provision as CI
repository secrets, named exactly as Tauri v2 expects them:

**macOS** (codesign + notarize):
- `APPLE_CERTIFICATE` — base64-encoded `.p12` signing certificate
- `APPLE_CERTIFICATE_PASSWORD`
- `APPLE_SIGNING_IDENTITY`
- `APPLE_ID`
- `APPLE_PASSWORD` — an app-specific password for notarization
- `APPLE_TEAM_ID`

**Windows** (Authenticode):
- `WINDOWS_CERTIFICATE` — base64-encoded `.pfx` signing certificate
- `WINDOWS_CERTIFICATE_PASSWORD`

Linux `.AppImage`/`.deb` artifacts are not signed by this pipeline.

These names and the env-var pass-through in `release.yml` follow Tauri v2's
documented signing conventions, but **have not been exercised against real
certificates** — nobody has provisioned these secrets yet. Confirm against
current Tauri docs before relying on this for an actual signed release.

## SBOM Tooling Notes

`@cyclonedx/cyclonedx-npm` (the standard CycloneDX generator for Node
projects) shells out to `npm ls` internally, which does not understand
pnpm's `node_modules` layout on this project — it errors outright, and a
related `pnpm import` attempt corrupted this repo's committed
`apps/desktop/pnpm-lock.yaml` during testing (recovered via `git restore`,
no lasting damage). `pnpm licenses list --json` was used instead: not
CycloneDX format, but accurate, safe, and pnpm-native. Revisit if a
pnpm-aware CycloneDX generator becomes available.
