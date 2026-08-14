# CorpusSieve Engine Protocol v1 (Specification)

## 1. Overview
The CorpusSieve Desktop Application communicates with the Python engine sidecar process over a bidirectional **NDJSON JSON-RPC 2.0 protocol** running over `stdin` (requests to engine) and `stdout` (responses and event notifications to client).

## 2. Framing
- Every message is a single-line UTF-8 JSON object ending with a newline `\n`.
- Stderr is reserved for low-level crash logging and is captured by the host application.

## 3. Handshake (`engine.hello`)
Upon sidecar launch, the desktop client MUST send `engine.hello`:

### Request
```json
{"jsonrpc": "2.0", "id": 1, "method": "engine.hello", "params": {"client_version": "0.1.0"}}
```

### Response
```json
{"jsonrpc": "2.0", "id": 1, "result": {"protocol_version": 1, "engine_version": "0.1.0.dev0"}}
```

If `protocol_version` does not match `1`, the client MUST abort execution.

## 4. Notifications (`event/*`)
Notifications are engine-initiated JSON-RPC objects without an `id` field:

### `event/progress`
```json
{
  "jsonrpc": "2.0",
  "method": "event/progress",
  "params": {
    "job_id": "job-123",
    "stage": "building",
    "pct": 45.0,
    "message": "Extracting articles from bz2 stream...",
    "elapsed_sec": 12.4
  }
}
```

## 5. Method Surface
- `engine.hello`: Handshake and protocol verification
- `project.create`: Initialize a new project directory
- `project.open`: Load an existing project directory
- `source.inspect`: InspectWikimedia dump files
- `metadata.build`: Build SQLite metadata database
- `model.detect`: Probe local Ollama/LMStudio providers
- `domain.compile`: Compile domain definition to lock
- `build.start`: Run extraction build job
- `corpus.validate`: Validate canonical corpus
- `export.markdown`: Export corpus to RAG Markdown
- `export.jsonl`: Export corpus to plain JSONL
