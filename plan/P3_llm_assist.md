# Phase P3 — Local AI Assistance (design milestone M3)

Goal: optional LLM assistance behind the `ModelProvider` interface — detection,
model listing, capability testing, intent→facets, boundary questions, and the
ambiguous-branch review hook (FR-006, FR-008–FR-011, FR-015). May run in
parallel with P4 once P2 is done.

Trust boundary (absolute, design §8.6): providers expose exactly one inference
entry point, `complete_structured`, whose output is parsed against a Pydantic
schema and used as data. No provider code executes shell commands. Detection is
HTTP-only against the two fixed loopback URLs plus user-entered endpoints — no
LAN scanning.

---

## P3.1 ModelProvider interface + provider registry
**Depends:** P0.3.

**Deliverables**
- `models/base.py` — `ModelProvider(ABC)` per design §8.1:
  `detect(cls) -> ProviderEndpoint | None` (probe default loopback URL,
  timeout 1.5 s), `health() -> bool`, `list_models() -> list[ModelInfo]`,
  `loaded_models() -> list[ModelInfo]`, `capability_test(model_id) ->
  CapabilityResult`, `complete_structured(model_id, schema: type[BaseModel],
  system: str, prompt: str, max_retries: int = 2) -> BaseModel`,
  `provider_metadata() -> dict`.
  `complete_structured` contract: request JSON output; parse; on parse/validation
  failure retry with the validation error appended to the prompt; after
  retries raise `CorpusSieveError(MODEL_SCHEMA_TEST_FAILED)`.
- `models/registry.py` — `detect_all() -> list[ProviderEndpoint]` (Ollama then
  LM Studio), `provider_for(endpoint) -> ModelProvider`.
- `models/config.py` — provider config persisted at
  `platformdirs.user_config_dir("corpussieve")/providers.yaml`
  (endpoints only); tokens stored via `keyring` under service
  `corpussieve`, referenced by `auth_token_ref` (design §21, §24). Non-loopback
  endpoint entries carry `is_loopback=False`; HTTPS URLs are never downgraded —
  reject `http://` rewrite of an `https://` entry.
- `models/errors.py` — failure classifier mapping httpx exceptions/status to
  exactly: `MODEL_UNREACHABLE`, `MODEL_AUTH_FAILED` (401/403),
  endpoint-mismatch (404 on known route → `MODEL_UNREACHABLE` with
  detail.kind="endpoint_mismatch"), "no models" (empty list is a result, not
  an error) — design §8.4 failure classes.

**Tests:** registry with both providers mocked via `respx`; token never
appears in providers.yaml (write config with token, grep file).

**DoD:** global DoD.

---

## P3.2 OllamaProvider
**Depends:** P3.1.

**Deliverables** — `models/ollama.py` (design §8.2):
- Base `http://127.0.0.1:11434`. `list_models` ← `GET /api/tags`;
  `loaded_models` ← `GET /api/ps`; `health` ← `GET /api/tags` 200.
- `complete_structured` ← native `POST /api/chat` with `"format":
  <json-schema>` (Ollama structured outputs), `"stream": false`,
  options `{"temperature": 0}`.
- Map tags/ps payload fields (name, size, details.family,
  details.parameter_size, context length when present) into `ModelInfo`.

**Tests** — `tests/models/test_ollama.py` with respx fixtures pinned from real
API shapes (record sample JSON into `tests/fixtures/providers/ollama/*.json`):
list/loaded parsing, structured completion happy path, malformed-JSON retry
then failure, 401 → MODEL_AUTH_FAILED, connect error → MODEL_UNREACHABLE.
Optional live test gated on env `CORPUSSIEVE_TEST_OLLAMA_URL` (skipped in CI).

**DoD:** global DoD.

---

## P3.3 LMStudioProvider
**Depends:** P3.1.

**Deliverables** — `models/lmstudio.py` (design §8.3):
- Base `http://127.0.0.1:1234`. `list_models`/`loaded_models` ← native
  `GET /api/v1/models` (report loaded instances; include embedding models in
  list with model_type="embedding" but exclude them from selectable chat
  models). Bearer token header when configured.
- `complete_structured` ← OpenAI-compatible `POST /v1/chat/completions` with
  `response_format: {type:"json_schema", json_schema:{…, strict:true}}`,
  temperature 0.
- Same failure classification and tests pattern as P3.2 (fixtures under
  `tests/fixtures/providers/lmstudio/`); live test env
  `CORPUSSIEVE_TEST_LMSTUDIO_URL`.

**DoD:** global DoD.

---

## P3.4 Capability test + `model detect` / `model test` CLI
**Depends:** P3.2, P3.3.

**Deliverables**
- `models/capability.py` — `run_capability_test(provider, model_id) ->
  CapabilityResult` (contracts addition `contracts/capability.py`, sanctioned):
  3 fixed prompts (committed in `models/prompts/capability_v1.py`, versioned
  constant `PROMPT_VERSION="cap-v1"`) asking for `BranchReviewResult`-shaped
  JSON about unambiguous toy inputs with known expected decisions.
  Score: 3/3 passed → `passed`; 2/3 → `warn` ("allowed with increased
  human review", design §8.5); else `failed`.
- `cli/model_cmds.py` —
  `corpussieve model detect [--json]`: probe both defaults, render table
  (provider, base_url, reachable, model count); provider-specific setup
  hints printed when not found (static text, no commands executed).
  `corpussieve model add --url URL [--provider ollama|lmstudio]`: validates
  reachability, classifies failure exactly per P3.1, warns on non-loopback
  (privacy note, design §8.4), prompts for token via hidden input when 401.
  `corpussieve model list [--json]`: all endpoints × models with loaded state
  and cached capability result.
  `corpussieve model test --model MODEL_ID [--endpoint URL] [--json]`: runs
  capability test, persists result to providers.yaml cache.

**Tests:** CliRunner with respx-mocked providers for every command and
failure class; non-loopback warning asserted.

**DoD**
```bash
cd engine && uv run corpussieve model detect --json
```
(succeeds with empty result on a machine with no providers) plus global DoD.

---

## P3.5 Intent→facets + boundary questions
**Depends:** P3.4, P2.1.

**Deliverables**
- `domain/intent.py` — `propose_facets(provider, model_id, intent: str,
  language: str) -> FacetProposal` and `propose_boundary_questions(provider,
  model_id, intent, facets) -> list[BoundaryQuestion]` (≤8 questions).
  Prompts live in `domain/prompts/intent_v1.py` with `PROMPT_VERSION=
  "intent-v1"`; prompts instruct the model to output **conceptual facets, not
  Wikipedia category names** (design §7.1 step 4). Facet strings are later
  resolved only through P2.2 local search — never trusted as categories.
- `apply_answers(defn, questions, answers) -> DomainDefinition` — pure
  function folding accepted answers into facets include/exclude lists.
- Upgrade `cli/domain_cmds.py::create`: when `--intent` given AND a configured
  model exists → run propose_facets, interactively ask boundary questions
  (Rich prompts; `--yes` accepts recommended defaults; `--no-llm` forces the
  P2.1 manual template). Resulting domain.yaml records provenance comment
  header (`# generated with <provider>/<model> intent-v1`). Without a model,
  behave exactly as P2.1 (FR-007 manual path must keep working).

**Tests:** mocked provider returns fixture FacetProposal → generated
domain.yaml validates and matches golden file; answers folding matrix;
`--no-llm` bypasses provider entirely (respx asserts zero calls).

**DoD:** global DoD.

---

## P3.6 Ambiguous-branch review + decision cache
**Depends:** P3.4, P2.3, P1.5.

**Deliverables**
- `domain/branch_review.py` — `LlmAmbiguousHook` implementing P2.3's
  `AmbiguousHook` protocol: builds the bounded context (domain definition,
  root, parent path, candidate, ≤10 sample child names, ≤10 sample member
  titles — nothing else; no article text), calls `complete_structured` with
  `BranchReviewResult`, prompt `branch-v1`.
  - Cache: before calling, look up
    `MetadataIndex.get_domain_decisions(domain_hash, source_fingerprint)`;
    after calling, `record_domain_decision` with provider/model/prompt_version
    (design §10 `domain_decisions` table).
  - `confidence < 0.7` or `needs_human_review` → return `review` (never a
    silent include/exclude, design §11.5); collected into lock warnings as
    `needs_review:<category>` and decisions with `source="llm"`, decision
    `review`. Categories left in `review` are treated as **excluded from
    expansion but flagged** — the CLI compile summary must list them and
    `domain compile --resolve-reviews` opens an interactive accept/reject
    loop writing `source="human"` decisions into the lock.
- Wire into `compile_lock`: new optional arg `provider_ctx` → passes
  LlmAmbiguousHook when policy.ambiguous_branch==review and a model is
  configured; fills `DomainLock.llm = LlmProvenance(...)`.
  **Lock reproducibility rule:** with a populated decision cache, recompiling
  produces an identical lock without any model calls (test asserts zero HTTP).

**Tests:** hook returns cached decision without HTTP; low-confidence →
review path; human resolution loop (CliRunner scripted input); lock recompile
determinism with warm cache; schema-invalid model output retries then fails
closed to `review` (not include).

**DoD:** global DoD; P2 traversal tests still pass unchanged (interface
unbroken).
