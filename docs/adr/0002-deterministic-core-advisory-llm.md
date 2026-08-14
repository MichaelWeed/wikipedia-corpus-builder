# ADR 0002: Deterministic Graph Compiler with Advisory LLM Assistance

- **Status:** Accepted
- **Date:** 2026-08-13
- **Deciders:** CorpusSieve Architecture Guild

## Context and Problem Statement

Building domain-specific corpora from Wikipedia dumps requires navigating vast category graphs. Purely heuristic graph traversals often suffer from scope creep or missed subtrees, while relying entirely on Large Language Models (LLMs) for extraction is non-deterministic, slow, and expensive.

## Decision Drivers

- 100% reproducible corpus generation given identical input dumps and domain locks.
- Security against LLM hallucination and prompt injection attacks embedded within wikitext dumps.
- Ability to leverage local LLMs (Ollama / LM Studio) for semantic guidance without compromising build determinism.

## Decision Outcome

Chosen Option: **Deterministic Core with Advisory LLM Assistance**.

### Implementation Details

- **Deterministic Compiler:** The category graph traversal engine (`corpussieve.domain`) strictly enforces explicit rules, breadcrumb depths, and facet matching logic.
- **Advisory LLM Boundary:** Local AI models are invoked strictly for non-binding recommendations (suggesting keyword facets, answering boundary disambiguation questions).
- **LLM Trust Boundary:** All LLM responses are treated as untrusted data, schema-validated using Pydantic (`BranchReviewResult`, `FacetProposal`), and recorded in `DomainLock` provenance.
- **Reproducibility Guarantee:** Once `domain.lock.json` is generated, the corpus build phase operates with zero LLM dependency.

## Consequences

- **Positive:** Guaranteed bit-identical reproducibility across different runs and systems.
- **Positive:** Zero vulnerability to prompt injection from untrusted Wiki content.
- **Negative:** Users must compile a domain lock before executing extraction.
