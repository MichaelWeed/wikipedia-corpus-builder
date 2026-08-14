# ADR 0006: API-Based Local Model Discovery (No Shell Executed Discovery)

- **Status:** Accepted
- **Date:** 2026-08-13
- **Deciders:** CorpusSieve Architecture Guild

## Context and Problem Statement

Local AI providers (Ollama, LM Studio) run as local HTTP server daemons on developer machines. Detecting installed models and endpoint capabilities via subprocess shell invocation (`ollama list`, executing CLI commands) is unreliable, platform-dependent, and introduces shell injection risks.

## Decision Drivers

- Security against shell command injection and subprocess execution vulnerabilities.
- Reliable cross-platform discovery over standard HTTP REST APIs.
- Secure storage of optional API tokens.

## Decision Outcome

Chosen Option: **API-Based Model Discovery via HTTP (`httpx`) and System Keyring**.

### Implementation Details

- **HTTP Discovery:** `corpussieve.models` queries provider endpoints strictly via HTTP GET requests using `httpx` (e.g. `http://localhost:11434/api/tags` for Ollama, `http://localhost:1234/v1/models` for LM Studio).
- **No Subprocess Exec:** Discovery never executes shell binaries or inspects CLI output.
- **Keyring Token Storage:** Optional authentication tokens are stored in and retrieved from the OS keyring (`keyring>=25`). `project.yaml` contains only `provider_ref` keyring references.

## Consequences

- **Positive:** Robust cross-platform behavior (works identically across macOS, Linux, Windows).
- **Positive:** Zero shell invocation security risks.
- **Negative:** Provider daemons must be running and listening on local loopback ports during model discovery.
