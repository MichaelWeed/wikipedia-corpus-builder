# CorpusSieve — Solution Design Document

**Status:** Draft v0.1  
**Baseline date:** 2026-08-13  
**Working project name:** CorpusSieve  
**Tagline:** Local-first domain corpus compiler for Wikimedia data  
**Intended license for project code:** Apache-2.0 (finalize before first public release)  

> CorpusSieve turns massive Wikimedia dumps into auditable, domain-specific, AI-ready corpora. A user can describe a domain such as “video games,” review and refine the proposed boundaries, preview what will be retained, build a filtered corpus, and optionally remove the original full dump after the filtered result is verified.

---

## 1. Executive Summary

Existing Wikimedia tooling solves pieces of the problem: downloading dumps, parsing XML, traversing categories, building offline ZIM files, or extracting text. It does not provide one local-first application that turns a natural-language domain request into a reproducible, explainable, domain-specific corpus and then safely exports only the content the user wants.

CorpusSieve fills that gap.

The project must support two equal interfaces:

1. **Expert CLI** — usable entirely from a terminal and suitable for automation.
2. **Desktop application** — macOS, Windows, and Linux installers that launch as a normal GUI application without opening terminal windows. The GUI must guide non-experts through source selection, optional local-model connection, domain definition, preview, build, validation, export, and optional cleanup.

The product is **local-first and deterministic by design**. An LLM may help interpret intent, propose domain facets, or classify ambiguous category branches, but the LLM never receives authority to execute shell commands, delete data, or mutate the source corpus. All final selection is materialized into a validated lock file and manifest before extraction or deletion.

The MVP targets **one Wikipedia language/project at a time** from an existing local dump. Multilingual synthesis, Wikidata expansion, automatic full-dump download, Wikimedia Enterprise Structured Contents, and direct AnythingLLM API ingestion are post-MVP adapters designed into the architecture but not required to ship v0.1.

---

## 2. Problem Statement

A user may have a full Wikipedia dump but only need a domain-specific subset for local RAG, search, research, or offline analysis. Today, the user must combine multiple tools and understand several implementation details:

- Wikipedia category graphs are cyclic and semantically noisy.
- A category depth such as `5` does not define a semantic domain.
- Article titles alone are insufficient for selection.
- A dump may be compressed as a single large file, so “delete everything except X” cannot mean deleting individual records in place.
- Wikitext needs normalization before common RAG tools can use it well.
- The user needs to know why an article was selected and what might have been missed.
- A non-expert should not need to install a Python environment, edit scripts, or operate a terminal.
- Local LLM servers have different discovery and model-management APIs.
- Destructive cleanup must not happen until the output has been built and validated.

CorpusSieve solves these as one product instead of a one-off script.

---

## 3. Product Principles

### 3.1 Local first
All corpus processing happens locally by default. No cloud LLM or hosted service is required. No telemetry is enabled by default.

### 3.2 Deterministic core, probabilistic assistance
The LLM helps compile intent into rules. It does not become the rule engine. Given the same source fingerprint, resolved domain lock, and software version, corpus selection must be reproducible.

### 3.3 Explainability is a first-class output
Every included article must have selection provenance sufficient to answer, “Why was this included?”

### 3.4 Non-destructive by default
The default workflow creates a new filtered corpus and retains the source. Source deletion is an explicit post-build action with validation and confirmation gates.

### 3.5 Domain is configuration, not code
“Sports,” “video games,” “aviation,” and “military history” must use the same engine. Domain-specific behavior is expressed through a schema-backed domain definition and its resolved lock.

### 3.6 Consumer-agnostic canonical corpus
AnythingLLM is an important target but must not define the internal format. CorpusSieve owns a canonical corpus format and produces adapters/exports for downstream tools.

### 3.7 No hidden shell automation
Desktop discovery and normal operation must use APIs and direct process execution, not generated shell commands. LLM output is never executed.

---

## 4. Goals

### MVP goals

- Run as an expert CLI on macOS, Windows, and Linux.
- Ship a normal desktop application on macOS, Windows, and Linux.
- Open without spawning visible terminal windows.
- Accept an existing local Wikipedia dump.
- Prefer and understand `pages-articles-multistream.xml.bz2` plus its index when present.
- Support sequential `pages-articles.xml.bz2` as a fallback.
- Detect or request companion metadata needed for high-quality category selection.
- Build a local category graph from Wikipedia metadata.
- Allow the user to describe a domain in natural language.
- Auto-detect local Ollama and LM Studio servers.
- Allow manual remote/local endpoint configuration.
- List available models and loaded/running status using provider APIs.
- Compile intent into a schema-valid domain definition.
- Ask high-value boundary questions before selection.
- Let the user edit/approve proposed roots, exclusions, and policy.
- Traverse category graphs safely with cycle protection and bounded depth.
- Optionally use an LLM to review ambiguous category branches.
- Preview selected article counts and representative samples before extraction.
- Generate a deterministic locked domain configuration.
- Generate an auditable article manifest.
- Extract only selected articles.
- Export canonical JSONL and RAG-oriented Markdown.
- Resume or safely cancel long-running jobs.
- Offer optional source deletion only after a verified successful build.
- Keep logs and a machine-readable build report.

### Post-MVP goals

- Multiple languages in one project.
- Cross-language Wikidata QID expansion.
- Wikimedia Enterprise Snapshot / Structured Contents source adapter.
- Guided download of full dumps.
- Community-maintained domain packs.
- Direct AnythingLLM API ingestion.
- Open WebUI / LlamaIndex / Qdrant exporters.
- Images and media extraction.
- Incremental corpus updates across dump versions.
- Additional Wikimedia projects and non-Wikimedia source adapters.

---

## 5. Non-Goals for MVP

- Perfect semantic classification of all Wikipedia content.
- Article-by-article LLM classification across millions of articles by default.
- Hosting an LLM inside CorpusSieve.
- Embedding/vectorizing the corpus inside CorpusSieve.
- Replacing AnythingLLM or other RAG platforms.
- Editing a compressed source dump in place.
- Automatic LAN scanning for LLM servers.
- Executing arbitrary commands suggested by a model.
- Full media/image preservation.
- Full edit history processing.
- Building a general web crawler.

---

## 6. Target Users

### Persona A — Expert developer
Wants reproducible CLI commands, YAML/JSON contracts, logs, resumable jobs, and automation-friendly exit codes.

### Persona B — Local-AI power user
Uses LM Studio or Ollama but is not comfortable writing extraction code. Wants to point at a dump, describe a domain, review results, and export to a RAG tool.

### Persona C — Data/research user
Needs an auditable domain subset and provenance rather than a black-box “AI selected these pages” result.

---

## 7. User Experience

## 7.1 Desktop first-run flow

1. **Create Project**
   - Project name.
   - Working directory.
   - Language/project inferred from source filename when possible.

2. **Choose Source**
   - Select a local dump file or directory.
   - Detect dump type, language, date, companion index, and metadata files.
   - Display source health and missing recommended files.
   - If companion metadata is missing and the source can be identified, offer to retrieve only the missing metadata from the official Wikimedia dump location. This may ship late in MVP if necessary.

3. **Connect AI — Optional**
   - Automatically probe:
     - Ollama: `http://127.0.0.1:11434`
     - LM Studio: `http://127.0.0.1:1234`
   - Do not scan arbitrary LAN addresses.
   - If a local server is found, list models and running/loaded state.
   - If not found, show provider-specific setup instructions.
   - Let the user enter a server URL manually.
   - For non-loopback endpoints, show a privacy/security note before use.
   - Support an authentication token where the provider supports one.
   - Run a small structured-output capability test before relying on the selected model.

4. **Describe Domain**
   - Natural-language prompt, e.g.:
     - “Keep only things related to video games.”
     - “Keep aviation and aerospace engineering, but not airline travel guides.”
   - The LLM or deterministic assistant extracts conceptual facets, not unverified Wikipedia category names.

5. **Clarify Boundaries**
   - The app proposes high-value questions based on the intent.
   - Example for video games:
     - Include esports?
     - Include video-game hardware/consoles?
     - Include companies, publishers, and developers?
     - Include game engines and development tools?
     - Include streamers/content creators?
     - Include gambling, board games, or tabletop games?
   - The user can accept recommended defaults.

6. **Resolve Domain**
   - Search actual local category metadata for category candidates.
   - Present candidate root categories with local counts.
   - The user may accept/edit.
   - Compile exclusions and traversal settings.
   - Optional LLM branch classification uses only bounded metadata/sample context.

7. **Preview**
   - Article count.
   - Estimated output size.
   - Counts by root and depth.
   - Representative included pages.
   - Representative excluded/borderline pages.
   - Suspected contamination groups.
   - “Why included?” inspection.
   - Warnings when selection is too broad or likely incomplete.

8. **Choose Build Mode**
   - **Extract and keep source** — default.
   - **Extract, verify, then purge source** — advanced.
   - The app must explain that compressed dumps cannot have individual articles deleted in place. Purge means creating the filtered output, verifying it, then deleting the original source file(s).

9. **Build**
   - Visible progress by stage.
   - Pause/cancel where technically safe.
   - Resumable state.
   - No destructive action during extraction.

10. **Validate**
    - Counts match manifest.
    - Required metadata present.
    - Output can be reopened.
    - Build report generated.
    - Optional sampling audit.

11. **Export**
    - Canonical JSONL/Zstandard.
    - Markdown directory suitable for RAG ingestion.
    - Manifest and attribution files.
    - Open output folder.
    - Direct AnythingLLM integration is post-MVP.

12. **Cleanup**
    - If user selected purge:
      - Show exact files and total size to be deleted.
      - Require explicit confirmation after validation.
      - Offer “move to Trash” and “permanent delete” when platform support permits.
      - Permanent delete must be a separate, stronger confirmation because Trash may not free disk space.

---

## 7.2 Expert CLI

Illustrative command contract:

```bash
corpussieve project init my-games-corpus

corpussieve source inspect \
  --source /data/enwiki-20260801-pages-articles-multistream.xml.bz2

corpussieve model detect

corpussieve domain create \
  --intent "Keep material related to video games"

corpussieve domain compile \
  --domain domains/video-games.yaml

corpussieve domain audit \
  --domain domains/video-games.yaml

corpussieve build \
  --domain domains/video-games.lock.json \
  --output /data/video-games-corpus

corpussieve export markdown \
  --corpus /data/video-games-corpus \
  --output /data/video-games-markdown
```

Destructive behavior must never be implied by `build`. A separate command is required:

```bash
corpussieve source purge \
  --project /data/video-games-corpus/project.yaml
```

The purge command must refuse to run unless the build state records a successful validation against the current source fingerprint.

---

## 8. Local Model Integration

## 8.1 Provider abstraction

```text
ModelProvider
├── detect()
├── health()
├── list_models()
├── loaded_models()
├── capability_test()
├── complete_structured(schema, prompt)
└── provider_metadata()
```

Initial adapters:

- `OllamaProvider`
- `LMStudioProvider`

Future adapters can implement the same interface without changing the domain engine.

## 8.2 Ollama

Use HTTP APIs rather than shelling out to `ollama ls`.

- Default local API base: `http://127.0.0.1:11434`
- `GET /api/tags` — available/downloaded models.
- `GET /api/ps` — currently running models.
- Native chat endpoint should be used for provider-specific structured output where practical.
- Ollama binds to loopback by default; remote/LAN use is an explicit user configuration concern.

## 8.3 LM Studio

- Default local server commonly uses port `1234`.
- Prefer the current native v1 model-management API.
- `GET /api/v1/models` returns available LLM and embedding models and their loaded instances.
- Inference may use the native API or OpenAI-compatible endpoint behind the provider adapter.
- Authentication token support must be supported when the server requires it.
- LM Studio can serve on localhost or a network address and can also support headless/service deployments.

## 8.4 Connection guidance

The UI must not ask novice users to “find your IP” without guidance.

For local use:
- First try localhost automatically.
- If detected, the user should not need to know an IP address.

For a remote machine:
- Ask the user which provider hosts the model.
- Show provider-specific steps for enabling network serving.
- Explain that the server machine’s LAN address is needed only for direct LAN connections.
- Provide OS-specific commands as copyable instructions only when needed; do not automatically execute network reconfiguration commands.
- Test the entered URL and report the exact failure class: unreachable, authentication failed, endpoint mismatch, or no models.

## 8.5 Model selection

Prefer a model already loaded/running, but do not silently switch or unload user models.

For each model display:
- Provider.
- Model name.
- Running/loaded status.
- Model type where available.
- Context length/capabilities where available.
- Result of CorpusSieve capability test.

The capability test checks whether the model can reliably return JSON matching the domain compiler schema. A weak model may still be allowed with a warning and increased human-review requirements.

## 8.6 Trust boundary

The LLM may:
- Turn user intent into conceptual facets.
- Suggest boundary questions.
- Classify ambiguous category branches.
- Review samples for likely false positives/negatives.
- Explain a proposed selection.

The LLM may not:
- Execute commands.
- Choose filesystem paths without user selection.
- Delete, move, or overwrite source files.
- Modify the locked manifest after approval without a recompile.
- Bypass schema validation.
- Decide that a failed validation can be ignored.

---

## 9. Source Data Architecture

## 9.1 MVP preferred source

Preferred local source:

```text
<lang>wiki-<date>-pages-articles-multistream.xml.bz2
<lang>wiki-<date>-pages-articles-multistream-index.txt.bz2
<lang>wiki-<date>-page.sql.gz
<lang>wiki-<date>-categorylinks.sql.gz
```

Why:
- Multistream plus index enables more efficient selective extraction than requiring a complete sequential decompression.
- `page` and `categorylinks` provide a clean local representation of page/category relationships.
- The source remains official Wikimedia data, without requiring a hosted third-party dataset.

Sequential `pages-articles.xml.bz2` remains supported as a fallback.

## 9.2 Source adapters

```text
SourceAdapter
├── inspect()
├── fingerprint()
├── build_metadata_index()
├── enumerate_pages()
├── extract_selected_pages()
└── source_metadata()
```

MVP:
- `WikimediaXmlDumpAdapter`

Post-MVP:
- `MediaWikiContentExportAdapter`
- `WikimediaEnterpriseSnapshotAdapter`
- `WikimediaStructuredContentsAdapter`

## 9.3 Source fingerprint

A project must detect source drift. Store:
- Project/language.
- Dump date if known.
- File names.
- Byte sizes.
- Modification timestamps.
- Fast local fingerprint.
- Official checksum when known/verified.
- Optional full local hash.

A destructive purge requires the source fingerprint at purge time to match the source used by the successful build.

---

## 10. Metadata Index

The engine must not load all Wikipedia metadata into RAM.

Build an on-disk metadata database, initially SQLite for minimal deployment complexity.

Suggested tables:

```text
pages(
  page_id INTEGER PRIMARY KEY,
  namespace INTEGER,
  title TEXT,
  is_redirect INTEGER
)

category_membership(
  page_id INTEGER,
  category TEXT,
  member_type TEXT
)

categories(
  category TEXT PRIMARY KEY,
  page_id INTEGER NULL
)

category_edges(
  parent_category TEXT,
  child_category TEXT
)

domain_decisions(
  domain_hash TEXT,
  source_fingerprint TEXT,
  category TEXT,
  decision TEXT,
  confidence REAL,
  reason TEXT,
  model_provider TEXT NULL,
  model_id TEXT NULL,
  prompt_version TEXT NULL
)
```

Indexes must support:
- Category → child categories.
- Category → direct article members.
- Page → categories.
- Category-name search.

The implementation may later migrate performance-sensitive indexing to DuckDB or Rust-native structures without changing the external contracts.

---

## 11. Domain Compiler

## 11.1 Core concept

A user’s natural-language intent is not the final selection rule.

Compilation pipeline:

```text
Natural-language intent
        ↓
Concept/facet proposal
        ↓
Local category search
        ↓
Validated root candidates
        ↓
Boundary questions
        ↓
Human-approved Domain Definition
        ↓
Graph traversal + optional LLM branch review
        ↓
Resolved Domain Lock
        ↓
Article Manifest
```

## 11.2 Domain Definition

Human-readable and editable YAML. It expresses intent and policy but may still contain unresolved semantic inputs.

Example:

```yaml
schema_version: 1
id: video-games
name: Video Games
description: >
  Video games, game development, gaming hardware, esports,
  companies, franchises, and related history.

language: en

policy:
  mode: balanced
  ambiguous_branch: review
  max_total_categories: 100000

facets:
  include:
    - video games
    - video game developers
    - video game publishers
    - consoles
    - game engines
    - esports
  exclude:
    - casino gambling
    - board games
    - tabletop role-playing games

roots:
  - query: Video games
    max_depth: 6

hard_exclude_pages: []
forced_include_pages: []
```

## 11.3 Domain Lock

The lock is machine-generated, reproducible, and source-specific.

It contains:
- Domain definition hash.
- Source fingerprint.
- Resolved category titles.
- Traversal rules.
- Explicit include/exclude branch decisions.
- LLM classification decisions.
- Model provider/model ID.
- Prompt/schema version.
- Human overrides.
- Compiler version.
- Compilation timestamp.
- Warnings acknowledged by the user.

**Build must consume the lock, not re-ask the LLM.**

This is the key reproducibility boundary.

## 11.4 Graph traversal semantics

- Category graph traversal must maintain a visited set and cannot loop.
- Each root has an explicit maximum depth.
- Global category and article limits act as runaway guards.
- An excluded category blocks traversal through that branch.
- Branch exclusion does **not** automatically hard-exclude an article reached independently through another valid branch.
- Hard article exclusion is a separate rule.
- Forced includes are explicit and recorded.
- Selection provenance retains at least one valid root/path reason per article.
- The compiler must detect suspicious explosive growth and pause for review.

## 11.5 LLM-assisted branch review

Default use of LLM should be **category-level**, not article-level.

For a candidate child category the classifier may receive:
- Domain definition.
- Current root.
- Parent path.
- Candidate category name.
- Small samples of child category names and article titles.
- No tool access.

Expected structured result:

```json
{
  "decision": "include",
  "confidence": 0.91,
  "reason": "Directly represents video-game hardware.",
  "needs_human_review": false
}
```

Responses are schema validated and cached.

Low-confidence responses become review items instead of silent decisions.

## 11.6 Selection modes

### High recall
- Ambiguous branches included or reviewed.
- Optimized to minimize legitimate omissions.
- More contamination expected.

### Balanced
- Ambiguous branches go to model/human review.
- Recommended default.

### High precision
- Ambiguous branches excluded unless approved.
- Optimized for a smaller cleaner corpus.

---

## 12. Manifest

The manifest is the authoritative list of selected pages.

Minimum record:

```json
{
  "schema_version": 1,
  "project": "enwiki",
  "language": "en",
  "page_id": 12345,
  "title": "Example game",
  "namespace": 0,
  "selected": true,
  "selection": {
    "root": "Video_games",
    "depth": 4,
    "via_category": "Example_game_genre",
    "reason_type": "category_path"
  }
}
```

After extraction, enrich with:
- Revision ID.
- Source offset/stream where applicable.
- Redirect aliases if captured.
- Content hash.
- Output document ID.

A separate compact provenance database may retain additional paths so the JSONL manifest does not grow excessively.

---

## 13. Extraction Engine

## 13.1 Multistream

When a multistream dump and index are available:
- Parse the index.
- Map selected pages to compressed stream offsets.
- Group extraction by stream offset.
- Decompress only streams that may contain selected pages.
- Parse pages in those streams and emit selected records.
- Never trust title alone when page ID is available.

## 13.2 Sequential fallback

For a non-multistream dump:
- Stream the BZip2 input once.
- Parse XML incrementally.
- Emit selected pages.
- Never fully decompress the entire XML to temporary disk as a prerequisite.

## 13.3 Resource bounds

MVP target:
- Bounded-memory streaming architecture.
- No design requiring the full dump or full graph in RAM.
- Back-pressure between decompression, parsing, normalization, and output.
- Progress checkpoints at stable extraction boundaries.

Exact performance targets should be established with benchmark fixtures before v0.1 release rather than guessed in advance.

---

## 14. Canonical Corpus

Canonical storage must preserve enough source fidelity that an exporter can be regenerated without re-reading the full source dump.

Recommended canonical artifact:

```text
corpus/
├── corpus.jsonl.zst
├── manifest.jsonl.zst
├── domain.yaml
├── domain.lock.json
├── build-report.json
├── attribution.json
└── project.yaml
```

Canonical article record:

```json
{
  "document_id": "enwiki:12345:987654321",
  "source": {
    "project": "enwiki",
    "language": "en",
    "page_id": 12345,
    "revision_id": 987654321,
    "title": "Example",
    "source_url": "https://en.wikipedia.org/wiki/Example",
    "dump_date": "2026-08-01"
  },
  "categories": ["..."],
  "selection": {"...": "..."},
  "content": {
    "format": "wikitext",
    "raw": "..."
  }
}
```

The canonical corpus may contain raw wikitext so normalization can improve over time without requiring the full original dump again.

---

## 15. RAG Normalization and Exports

## 15.1 Markdown exporter

One document per article, preserving useful headings.

Example:

```markdown
---
source: wikipedia
project: enwiki
language: en
title: Example
page_id: 12345
revision_id: 987654321
license: CC BY-SA 4.0
---

# Example

## History

...

## Gameplay

...
```

Goals:
- Remove markup noise that harms retrieval.
- Preserve semantic headings.
- Preserve useful list content.
- Preserve useful infobox facts when reliably parsable.
- Remove navigation/template boilerplate.
- Handle references consistently.
- Avoid pretending that normalization is lossless.

The parser must be behind a replaceable `Normalizer` interface. MVP may use mature wikitext parsing libraries, but tests must define expected output rather than depending on a specific parser forever.

## 15.2 JSONL exporter

For developers and other ingestion systems.

## 15.3 AnythingLLM profile

MVP:
- Produce an AnythingLLM-friendly Markdown folder.
- Provide instructions to ingest/exported documents.

Post-MVP:
- Connect to AnythingLLM Developer API.
- Select/create workspace.
- Upload documents.
- Embed them.
- Record ingestion status.

CorpusSieve must never depend on AnythingLLM’s internal storage directory layout.

---

## 16. Delete / Purge Design

## 16.1 Important semantic rule

A compressed Wikipedia dump is not treated as a mutable database.

“Keep video games and delete everything else” means:

1. Build a new filtered canonical corpus.
2. Validate that corpus.
3. Optionally export normalized files.
4. Confirm exactly which original files will be removed.
5. Remove the original source only after validation succeeds.

## 16.2 Purge preconditions

Purge must fail unless:
- Build status is `SUCCEEDED`.
- Validation status is `PASSED`.
- Current source fingerprint matches build source fingerprint.
- Canonical corpus is readable.
- Manifest count equals extracted document count or documented redirect policy.
- Output path is not inside a directory scheduled for deletion.
- The user explicitly requested purge mode.

## 16.3 Desktop confirmation

The UI must show:
- Source paths.
- Total bytes.
- Whether deletion is reversible.
- Corpus output path.
- Build report status.
- A warning that another domain will require re-downloading source data.

Permanent deletion requires a separate explicit confirmation such as typing the project name or a generated phrase.

## 16.4 CLI confirmation

`source purge` is a separate command.

Interactive mode:
- Show deletion plan.
- Require confirmation.

Non-interactive automation:
- Require a deliberately named flag.
- Still enforce all build/validation invariants.
- No `--force` flag may bypass source fingerprint mismatch or failed validation.

---

## 17. Application Architecture

Recommended MVP architecture:

```text
┌─────────────────────────────────────┐
│         Tauri v2 Desktop UI         │
│        React + TypeScript/Vite      │
└──────────────────┬──────────────────┘
                   │ structured IPC
┌──────────────────▼──────────────────┐
│   CorpusSieve Engine Sidecar        │
│   Python packaged as standalone     │
│                                     │
│  CLI + domain compiler + graph      │
│  source adapters + extraction       │
│  normalization + validation         │
└───────┬─────────┬─────────┬────────┘
        │         │         │
        ▼         ▼         ▼
   Wikimedia    Ollama   LM Studio
   local data    API       API
```

### Why this split

- Python minimizes time-to-MVP for MediaWiki parsing, data tooling, schemas, and CLI development.
- Tauri v2 provides a native desktop shell across macOS, Windows, and Linux.
- Tauri supports bundled sidecar binaries, so end users do not need Python installed.
- The same Python package can expose the expert CLI and the desktop engine protocol.
- Performance-sensitive modules can later be rewritten in Rust behind stable interfaces without redesigning the product.

### Desktop launch behavior

- GUI build launches normally from Finder/Explorer/application menu.
- No visible console window.
- Engine launches as a child sidecar through Tauri, not through a shell.
- Logs go to application log files and an in-app log viewer.
- A distinct console-enabled CLI binary/package remains available to experts.

---

## 18. Suggested Repository Layout

```text
corpussieve/
├── README.md
├── LICENSE
├── NOTICE
├── CONTRIBUTING.md
├── SECURITY.md
├── AGENTS.md
├── apps/
│   └── desktop/
│       ├── src/
│       └── src-tauri/
├── engine/
│   ├── pyproject.toml
│   ├── src/corpussieve/
│   │   ├── cli/
│   │   ├── api/
│   │   ├── sources/
│   │   ├── metadata/
│   │   ├── domain/
│   │   ├── models/
│   │   ├── extraction/
│   │   ├── normalization/
│   │   ├── validation/
│   │   ├── exporters/
│   │   └── safety/
│   └── tests/
├── schemas/
├── examples/
│   └── domains/
├── docs/
│   ├── SOLUTION_DESIGN.md
│   ├── MVP_SPEC.md
│   ├── DOMAIN_SPEC.md
│   ├── DATA_CONTRACTS.md
│   ├── UX_SPEC.md
│   ├── TEST_STRATEGY.md
│   ├── ROADMAP.md
│   └── adr/
└── .github/
    ├── workflows/
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

---

## 19. Desktop Technology

**Tauri v2** is the recommended shell.

Rationale:
- Cross-platform desktop packaging.
- Native application window instead of opening a browser.
- Support for bundling external sidecar binaries.
- Fine-grained permissions/capabilities.
- macOS and Windows distribution/signing documentation.
- Smaller runtime footprint than bundling a full Chromium runtime.

Recommended UI:
- React + TypeScript + Vite.
- Keep state management simple in MVP.
- Long-running jobs stream structured progress events from the engine.

The engine-sidecar protocol should be versioned JSON messages, not scraped stdout text.

---

## 20. Engine Technology

MVP recommendation:
- Python 3.12+ for source.
- Pydantic v2 for contracts.
- Typer for CLI.
- Rich for CLI progress/output.
- HTTP client behind provider adapters.
- SQLite for metadata/state.
- Streaming XML and BZip2 processing.
- Replaceable wikitext parser/normalizer.

Distribution:
- Build a standalone engine sidecar per OS/architecture.
- The desktop bundle includes the correct sidecar.
- CLI can be distributed through Python packaging initially and later as standalone binaries.

Do not make the end user install:
- Python.
- Node.js.
- Rust.
- Docker.
- Git.

Those are developer dependencies only.

---

## 21. Project Persistence

Each CorpusSieve project stores:

```text
project-root/
├── project.yaml
├── domain.yaml
├── domain.lock.json
├── state.sqlite
├── reports/
├── cache/
└── output/
```

`project.yaml` includes:
- Project ID.
- Source path(s).
- Source adapter.
- Source fingerprint.
- Working/output paths.
- Selected provider configuration reference.
- Current domain definition.
- Current build state.

Secrets such as remote API tokens must not be written in plaintext project YAML. Use the OS credential/keychain facility or an encrypted application secret store.

---

## 22. Job State Machine

Long-running operations must have explicit state.

```text
NEW
  ↓
SOURCE_INSPECTED
  ↓
METADATA_INDEXING
  ↓
METADATA_READY
  ↓
DOMAIN_DRAFT
  ↓
DOMAIN_COMPILED
  ↓
PREVIEWED
  ↓
BUILDING
  ↓
BUILD_SUCCEEDED
  ↓
VALIDATING
  ↓
VALIDATED
  ↓
EXPORTED
  ↓
OPTIONAL_SOURCE_PURGED
```

Failure/cancellation states preserve enough checkpoint data to resume safely.

A failed job must never be mistaken for a completed job after application restart.

---

## 23. Progress and Resumability

Each long job emits structured events:

```json
{
  "job_id": "uuid",
  "stage": "extract",
  "completed_units": 1024,
  "total_units": 9000,
  "message": "Processing multistream group 1024/9000"
}
```

Checkpoints should occur:
- During metadata ingestion.
- Per logical multistream group or safe sequential range.
- During normalization/export batches.

Partial output must be written to a temporary/staging location and only promoted atomically after validation.

---

## 24. Security and Privacy

### Default posture

- No telemetry.
- No cloud requests except user-selected official source downloads or explicitly configured model endpoints.
- Localhost model detection only.
- No arbitrary LAN scanning.
- No arbitrary code execution.
- No LLM tool execution.
- No shell command generation/execution from model output.
- Source files are read-only until an explicit post-validation purge action.

### Model endpoint security

If endpoint is not loopback:
- Mark it as remote/network.
- Explain that domain intent and category metadata may be sent to that endpoint.
- Allow user to disable sending article samples.
- Store tokens securely.
- Use HTTPS when supplied; do not silently downgrade HTTPS to HTTP.

### Untrusted corpus content

Wikipedia content and metadata are untrusted input.
- Never interpret article text as instructions.
- Do not pass raw article content into an agent with tools.
- Parser errors must not escape filesystem boundaries.
- Generated filenames must be sanitized.
- Archive/path traversal must be prevented.

---

## 25. Licensing and Attribution

### Project code

Recommended license: **Apache-2.0**.

Reasons:
- Permissive.
- Explicit patent grant.
- Familiar to commercial and OSS contributors.

Finalize through a standard license template before public release.

### Wikimedia content

Generated corpora do not become Apache-2.0 merely because CorpusSieve produced them.

The application must preserve source and attribution metadata. Wikimedia text is generally available under Creative Commons Attribution-ShareAlike terms, with project-specific and media-specific considerations.

Each export should include:
- Source project.
- Article title.
- Revision/page identifiers when available.
- Source URL.
- Dump date.
- Relevant license identifier.
- `ATTRIBUTION.md` or machine-readable attribution manifest.

Documentation must state that CorpusSieve is not affiliated with or endorsed by the Wikimedia Foundation and users remain responsible for compliance with source-content licensing.

---

## 26. Audit and Quality Report

Every build produces a report containing:

- Source identity/fingerprint.
- CorpusSieve version.
- Domain definition hash.
- Lock hash.
- Model/provider used during compilation, if any.
- Total categories traversed.
- Total categories included/excluded/reviewed.
- Total selected articles.
- Article counts by root.
- Counts by traversal depth.
- Forced includes/excludes.
- Warnings.
- Random included sample.
- Borderline/excluded sample.
- Extraction count.
- Normalization errors.
- Output size.
- Validation result.
- Whether source purge is eligible.

The desktop dashboard should render this report; the CLI should output JSON with `--json`.

---

## 27. MVP Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Inspect local Wikimedia XML dump | Must |
| FR-002 | Detect language/project/date when encoded in filename | Must |
| FR-003 | Detect multistream index and metadata companions | Must |
| FR-004 | Build persistent local category metadata index | Must |
| FR-005 | Create/edit domain definition | Must |
| FR-006 | Accept natural-language domain intent with configured local LLM | Must |
| FR-007 | Operate without an LLM using manual domain configuration | Must |
| FR-008 | Auto-detect Ollama on localhost | Must |
| FR-009 | Auto-detect LM Studio on localhost | Must |
| FR-010 | List installed/available and running/loaded models | Must |
| FR-011 | Test model structured-output capability | Must |
| FR-012 | Resolve actual local categories; never trust invented category names | Must |
| FR-013 | Traverse category graph with cycle/depth/runaway protection | Must |
| FR-014 | Support explicit branch exclusions and page overrides | Must |
| FR-015 | Optional LLM ambiguous-branch classification | Must |
| FR-016 | Generate source-specific domain lock | Must |
| FR-017 | Preview counts and samples | Must |
| FR-018 | Generate article selection manifest with provenance | Must |
| FR-019 | Selectively extract from multistream dumps | Must |
| FR-020 | Sequential extraction fallback | Must |
| FR-021 | Produce canonical compressed JSONL corpus | Must |
| FR-022 | Produce Markdown RAG export | Must |
| FR-023 | Generate build/audit report | Must |
| FR-024 | Resume interrupted long jobs | Must |
| FR-025 | Never delete source during normal build | Must |
| FR-026 | Optional post-validation source purge | Must |
| FR-027 | Desktop GUI with no visible terminal window | Must |
| FR-028 | Equivalent expert CLI for core operations | Must |
| FR-029 | Local logs and in-app progress | Must |
| FR-030 | Preserve attribution/source metadata | Must |

---

## 28. Non-Functional Requirements

### Reliability
- Build is idempotent for the same source + lock + version.
- Partial failures do not corrupt the source.
- Atomic promotion of completed output.
- Resume metadata survives restart.

### Performance
- Streaming architecture.
- Bounded memory.
- Multistream selective access when possible.
- No mandatory full decompression to disk.
- Batch model classification.

### Portability
- macOS desktop.
- Windows desktop.
- Linux desktop.
- CLI on all three.

### Accessibility
- Keyboard-navigable desktop controls.
- Meaningful progress labels.
- No status conveyed only by color.
- Logs/errors copyable as text.

### Observability
- Structured logs.
- Correlation/job IDs.
- User-facing error codes.
- `--json` CLI mode.

### Privacy
- No telemetry by default.
- Model endpoint use disclosed.
- Remote calls visible in project report.

---

## 29. Error Model

Errors must be categorized, not dumped as raw stack traces in the main UI.

Examples:

```text
SOURCE_UNSUPPORTED
SOURCE_COMPANION_MISSING
SOURCE_CHECKSUM_MISMATCH
METADATA_PARSE_FAILED
MODEL_UNREACHABLE
MODEL_AUTH_FAILED
MODEL_SCHEMA_TEST_FAILED
DOMAIN_ROOT_UNRESOLVED
DOMAIN_RUNAWAY_GROWTH
DOMAIN_REVIEW_REQUIRED
EXTRACTION_PARSE_FAILED
OUTPUT_DISK_INSUFFICIENT
VALIDATION_FAILED
PURGE_SOURCE_CHANGED
PURGE_OUTPUT_UNVERIFIED
```

Expert mode exposes stack trace/log detail.

---

## 30. Disk Safety

Before build:
- Determine free space on output volume.
- Estimate canonical output using selected page counts and sampled/source metadata when possible.
- Account for staging/temp space.
- Refuse obviously unsafe builds.
- Let experts override only non-integrity warnings.

Before purge:
- Confirm canonical output is on durable storage.
- Confirm staging files are not mistaken for final output.
- Confirm delete targets do not include output.
- Report expected space reclaimed.

---

## 31. Domain Pack Concept

A future community feature should be designed in now.

A **Domain Pack** is a versioned, testable set of domain definitions and expected quality samples.

Example:

```text
domain-packs/
└── video-games/
    ├── domain.yaml
    ├── README.md
    ├── tests/
    │   ├── must-include.txt
    │   └── must-exclude.txt
    └── language-overrides/
        ├── en.yaml
        └── es.yaml
```

This permits:
- Curated community domains.
- Repeatable tests against new dump versions.
- Natural-language users to start from a vetted pack instead of compiling from scratch.
- Separation of domain knowledge from application code.

---

## 32. Testing Strategy

### Unit
- Domain schema validation.
- Category title normalization.
- Cycle detection.
- Depth semantics.
- Branch exclusion semantics.
- Forced include/exclude precedence.
- Manifest provenance.
- Purge preconditions.
- Path traversal protection.
- Provider response parsing.

### Golden fixtures
Commit small synthetic MediaWiki dump/metadata fixtures that cover:
- Cyclic categories.
- Redirects.
- Multiple valid inclusion paths.
- Excluded subtree reachable from another root.
- Unicode titles.
- Malformed wikitext.
- Namespace filtering.

### Provider contract tests
Mock current Ollama and LM Studio API responses.

Optional live tests:
- Run only when developer environment variables identify a live provider.
- Never required in ordinary CI.

### Integration
- Build metadata index.
- Compile a domain.
- Generate manifest.
- Extract fixture corpus.
- Export Markdown.
- Validate.
- Simulate restart/resume.

### Destructive safety
Automated tests must prove:
- Build never deletes source.
- Failed validation blocks purge.
- Changed source blocks purge.
- Output-inside-delete-target blocks purge.
- Path symlink/canonicalization attacks cannot escape permitted scope.

### Desktop E2E
- First-run wizard.
- Model auto-detection mocks.
- Source selection.
- Domain approval.
- Build progress.
- Error recovery.
- Purge confirmation.

---

## 33. Release Engineering

GitHub Actions matrix should cover:
- Python tests: Linux/macOS/Windows.
- Desktop frontend tests.
- Tauri builds per target OS.
- Lint/type-check.
- Schema compatibility tests.

Public desktop release readiness requires:
- macOS Developer ID signing and notarization.
- Windows code signing to reduce untrusted-app warnings.
- Linux AppImage and at least one common package format.
- Published checksums.
- SBOM generation.
- Reproducible release notes.

Signing secrets must exist only in CI secret storage.

---

## 34. Open-Source Governance

Before public v0.1:
- Apache-2.0 license file.
- `CONTRIBUTING.md`.
- `SECURITY.md`.
- Code of Conduct.
- Issue templates.
- Pull-request template.
- Versioning policy.
- Supported-platform matrix.
- Security-contact mechanism.
- Clear statement that project is not affiliated with Wikimedia Foundation, Ollama, LM Studio, or AnythingLLM.

Recommended contribution model:
- GitHub issues/discussions.
- DCO sign-off rather than a custom CLA initially.
- Architecture changes require an ADR.
- Schema changes require compatibility notes.

---

## 35. Architecture Decision Records

Initial ADRs:

- ADR-0001: Tauri v2 desktop + packaged Python sidecar.
- ADR-0002: Deterministic selection core; LLM is advisory.
- ADR-0003: Non-destructive build and separate verified purge.
- ADR-0004: Domain definition + source-specific domain lock.
- ADR-0005: Canonical corpus independent of RAG consumer.
- ADR-0006: API-based local-model discovery; no CLI shell discovery.

---

## 36. MVP Milestones

### M0 — Repository and contracts
- Repo initialized.
- License/governance.
- Schemas.
- Synthetic fixtures.
- CI.
- ADRs.

### M1 — Source inspection and metadata
- Dump inspection.
- Fingerprinting.
- `page` / `categorylinks` ingestion.
- Category graph queries.
- CLI inspection commands.

### M2 — Deterministic domain compiler
- Domain YAML.
- Root resolution.
- Traversal.
- Exclusions.
- Preview.
- Manifest.
- No LLM required yet.

### M3 — Local AI assistance
- Ollama adapter.
- LM Studio adapter.
- Capability test.
- Intent-to-facet compiler.
- Boundary-question generation.
- Ambiguous-branch review.
- Domain lock.

### M4 — Extraction and canonical corpus
- Multistream selective extraction.
- Sequential fallback.
- Checkpoint/resume.
- JSONL/Zstandard corpus.
- Build report.

### M5 — RAG export
- Wikitext normalization.
- Markdown export.
- Attribution.
- AnythingLLM ingestion guide.

### M6 — Desktop application
- Tauri shell.
- Wizard/dashboard.
- Job progress.
- Settings/model UI.
- Expert mode.

### M7 — Safe purge and release hardening
- Purge workflow.
- Destructive tests.
- Signing/notarization.
- Cross-platform installers.
- Public v0.1.

---

## 37. Post-MVP Roadmap

### v0.2
- Official dump downloader.
- Automatic missing companion metadata retrieval.
- Better domain-quality metrics.
- Domain pack library.

### v0.3
- Multilingual projects.
- Wikidata QID cross-language expansion.
- Language-specific domain overrides.

### v0.4
- Wikimedia Enterprise Snapshot / Structured Contents adapters.
- Higher-fidelity sections, infoboxes, lists, and references.

### v0.5
- AnythingLLM API integration.
- Additional RAG exporters.
- Incremental refresh from newer dumps.

### v1.0
- Stable schemas.
- Proven domain-pack compatibility.
- Mature update/migration path.
- Broad performance benchmark suite.
- Documented plugin SDK for new sources/exporters.

---

## 38. Key Acceptance Criteria for v0.1

v0.1 is not complete until all are true:

1. A novice can install and launch the desktop app without seeing a terminal window.
2. An expert can complete the same core workflow from CLI.
3. An existing Wikimedia dump can be inspected without full decompression.
4. A local Ollama or LM Studio server can be detected through API.
5. Available and loaded/running models are visible to the user.
6. “Keep things related to video games” can become a user-reviewed domain definition.
7. All selected roots are verified against the local source metadata.
8. Category traversal cannot loop indefinitely.
9. The user can preview and inspect why pages are selected.
10. A resolved lock is produced before build.
11. The build consumes the lock and does not ask the LLM to improvise new rules.
12. The selected corpus can be extracted from a real multistream dump.
13. Canonical JSONL and Markdown exports are produced.
14. The build can resume after interruption.
15. The original source remains unchanged after ordinary build.
16. Source purge cannot occur after a failed validation or changed source.
17. A successful purge clearly reports what was removed and what was retained.
18. Every exported article carries source/attribution metadata.
19. CI passes on macOS, Windows, and Linux.
20. A clean machine does not need Python/Node/Rust installed to run the desktop release.

---

## 39. Current Upstream Facts Verified for This Design

Verified against official documentation on 2026-08-13:

- Ollama local API defaults to `http://localhost:11434/api`.
- Ollama `GET /api/tags` lists available models.
- Ollama `GET /api/ps` lists running models.
- Ollama binds to `127.0.0.1:11434` by default; LAN exposure is configured separately.
- LM Studio can serve models on localhost or a network address.
- LM Studio’s native v1 REST API includes `GET /api/v1/models` and reports loaded instances.
- Tauri v2 supports bundled external sidecar binaries.
- Wikimedia continues to publish multistream article dumps and indexes.
- Wikimedia `categorylinks` represents page membership in categories.
- Wikimedia Enterprise offers Snapshot and Structured Contents data, making it a useful future source adapter.
- AnythingLLM supports local embedding providers including Ollama and LM Studio; CorpusSieve should export to it rather than depend on its private storage layout.

Official reference URLs are recorded in `docs/REFERENCES.md`.

---

## 40. Final Architecture Position

CorpusSieve is **not** a Wikipedia trimming script.

It is a local-first **domain corpus compiler** with Wikipedia as the first source adapter.

Its unique value is the pipeline:

```text
Human intent
   ↓
Auditable domain definition
   ↓
Verified local source taxonomy
   ↓
Deterministic resolved lock
   ↓
Explainable manifest
   ↓
Selective extraction
   ↓
Canonical corpus
   ↓
RAG/export adapters
```

That is the problem existing individual OSS utilities do not solve as one product, and it gives the project room to expand beyond Wikipedia without redesigning the core.
