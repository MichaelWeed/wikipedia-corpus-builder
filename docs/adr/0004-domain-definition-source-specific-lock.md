# ADR 0004: Decoupled Domain Definition and Source-Specific Lock

- **Status:** Accepted
- **Date:** 2026-08-13
- **Deciders:** CorpusSieve Architecture Guild

## Context and Problem Statement

A domain definition (e.g. "Video Games Corpus") should be reusable across different language dumps or updated dump dates over time. However, resolving category graphs against a specific dump snapshot produces dump-specific category memberships and article selections.

## Decision Drivers

- Reusability of domain definitions across different dump snapshots and languages.
- Reproducibility of builds targeting a specific dump.
- Clear separation between intent (user specification) and compilation resolution (resolved graph).

## Decision Outcome

Chosen Option: **Decoupled DomainDefinition and DomainLock Artifacts**.

### Implementation Details

- **`domain.yaml` (`DomainDefinition`)**: User-editable, high-level intent specification containing query roots, selection policies, and inclusion/exclusion facets. Portable across dump versions.
- **`domain.lock.json` (`DomainLock`)**: Machine-generated, immutable resolution lock tied directly to a specific dump's `SourceFingerprint`. Contains all resolved category decisions, article manifests, compiler version, and cryptographic `lock_hash`.

## Consequences

- **Positive:** Domain definitions can be checked into version control, shared in domain packs, and re-used against future Wikimedia dumps.
- **Positive:** Domain locks serve as immutable receipts proving exact selection state for published datasets.
