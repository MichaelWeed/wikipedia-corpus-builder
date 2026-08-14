# Releasing CorpusSieve

This document describes the release engineering, versioning, code signing, and release procedures for CorpusSieve.

## Supported OS Matrix
- macOS (Apple Silicon arm64 & Intel x86_64) — `.dmg` installer & standalone executable
- Windows 10/11 (x64) — `.msi` / NSIS installer
- Linux (x86_64) — `.AppImage` & `.deb` packages

## Release Checklist

1. Verify all 20 acceptance criteria in `docs/ACCEPTANCE_V0_1.md`.
2. Run full test suite locally:
   ```bash
   cd engine
   uv run ruff check . && uv run ruff format --check .
   uv run mypy src
   uv run pytest -q
   ```
3. Tag release:
   ```bash
   git tag -a v0.1.0-rc1 -m "CorpusSieve v0.1.0-rc1 release candidate"
   git push origin v0.1.0-rc1
   ```
4. GitHub Actions release pipeline (`.github/workflows/release.yml`) will build sidecars, installers, checksums, and draft the release.

## Code Signing Secrets

When provisioning signing certificates in CI repository secrets:
- `APPLE_CERT` / `APPLE_ID` / `NOTARY_*` for macOS notarytool signing.
- `WINDOWS_CERT_*` for Windows signtool code signing.

If secrets are omitted, the pipeline gracefully produces unsigned release candidates with a clear warning notice.
