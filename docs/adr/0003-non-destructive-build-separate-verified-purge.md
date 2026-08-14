# ADR 0003: Non-Destructive Build Pipeline with Separate Verified Purge

- **Status:** Accepted
- **Date:** 2026-08-13
- **Deciders:** CorpusSieve Architecture Guild

## Context and Problem Statement

MediaWiki source dumps (XML/SQL files) are large multi-gigabyte downloads. Users working under tight disk constraints need the ability to reclaim disk space after building a canonical corpus without risking data loss from incomplete or corrupted builds.

## Decision Drivers

- Absolute protection against accidental deletion of raw source dumps.
- Guaranteed integrity verification of extracted output prior to any deletion.
- Auditability of destructive filesystem operations.

## Decision Outcome

Chosen Option: **Non-Destructive Build with Separate Verified Purge**.

### Implementation Details

- **Read-Only Dumps:** All source dump files are treated as read-only by default throughout the metadata, compilation, and extraction phases.
- **Isolated Purge Module:** `corpussieve.safety.purge` is the single, isolated module authorized to perform deletion of source dump files.
- **Precondition Verification:** Purge operations strictly enforce precondition checks:
  1. Build report status must be `VALIDATED` and output verification passed.
  2. Source file hash must match original `SourceFingerprint`.
  3. Output corpus path must be verified on durable storage distinct from temp paths.
- **Explicit Confirmation:** Purges require explicit CLI flags (`--purge-confirmed`) or explicit double-confirmation prompts in the desktop UI.

## Consequences

- **Positive:** Zero risk of source data destruction during failed or partial builds.
- **Positive:** Clear audit trail and disk safety preconditions.
- **Negative:** Requires temporary extra disk capacity during the extraction phase until purge is executed.
