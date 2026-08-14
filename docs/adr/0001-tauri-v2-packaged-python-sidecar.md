# ADR 0001: Tauri v2 + Packaged Python Sidecar Architecture

- **Status:** Accepted
- **Date:** 2026-08-13
- **Deciders:** CorpusSieve Architecture Guild

## Context and Problem Statement

CorpusSieve requires a high-performance desktop user interface while maintaining a robust, CLI-accessible Python engine for data parsing, graph traversal, and corpus extraction. The solution must support cross-platform desktop packaging (macOS, Windows, Linux) without bundling heavyweight runtime overhead like full Electron binaries.

## Decision Drivers

- Cross-platform desktop support with minimal binary size and low memory overhead.
- Clean separation between core execution logic (Python 3.12 engine) and user interface (React 18 + TypeScript + Vite).
- Standalone execution without requiring system Python installation for end users.

## Considered Options

1. Electron with embedded Python process.
2. Web browser interface (Flask/FastAPI local server).
3. Tauri v2 (Rust shell + Webview) with PyInstaller packaged Python sidecar binary (`externalBin`).

## Decision Outcome

Chosen Option: **Option 3 — Tauri v2 + Packaged Python Sidecar**.

### Implementation Details

- **Frontend:** React 18, Vite, TypeScript (strict mode), state managed via Zustand.
- **Desktop Shell:** Tauri v2 (Rust stable).
- **Engine Sidecar:** Python 3.12 core engine packaged via PyInstaller into OS-specific one-dir executables and invoked via Tauri `externalBin`.
- **IPC Protocol:** Engine Protocol v1 over stdio using line-delimited NDJSON JSON-RPC 2.0.

## Consequences

- **Positive:** Extremely small desktop binary size (<15 MB installer shell) and minimal idle RAM usage (~30-50 MB).
- **Positive:** Complete decoupling: python engine remains 100% usable as an independent CLI tool (`corpussieve`).
- **Negative:** Requires cross-compilation matrix setup for PyInstaller sidecars on Linux, macOS, and Windows in CI.
