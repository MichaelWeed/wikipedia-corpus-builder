# CorpusSieve — User Experience & Interface Spec (UX_SPEC)

CorpusSieve provides two complementary user interfaces operating over the same underlying engine:

1. **Command Line Interface (CLI)**:
   - High-throughput scriptable binary (`corpussieve`).
   - Standard output formatting via `rich` console tables, progress bars, and colored status badges.

2. **Desktop Application (Tauri v2 + React)**:
   - Guided multi-step wizard for project initialization, source selection, domain creation, and build monitoring.
   - Real-time engine protocol integration via stdio NDJSON JSON-RPC 2.0 sidecar.
