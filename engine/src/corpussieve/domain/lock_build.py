import json
from datetime import UTC, datetime
from pathlib import Path

from corpussieve import __version__
from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.enums import AmbiguousBranchPolicy
from corpussieve.contracts.lock import (
    DomainLock,
    LlmProvenance,
)
from corpussieve.contracts.lock import (
    ResolvedRoot as LockResolvedRoot,
)
from corpussieve.domain.branch_review import LlmAmbiguousHook
from corpussieve.domain.definition import domain_hash
from corpussieve.domain.resolve import resolve_exclusions, resolve_roots
from corpussieve.domain.traverse import AmbiguousHook, TraversalResult, traverse
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.models.base import ModelProvider


def compile_lock(
    defn: DomainDefinition,
    index: MetadataIndex,
    source_fingerprint: str,
    on_ambiguous: AmbiguousHook | None = None,
    provider_ctx: tuple[ModelProvider, str] | None = None,
    llm_provenance: LlmProvenance | None = None,
    acknowledged_warnings: tuple[str, ...] | list[str] = (),
) -> tuple[DomainLock, TraversalResult]:
    """Compile domain definition and metadata index into deterministic DomainLock."""
    root_res = resolve_roots(defn, index)
    explicit_ex, facet_ex = resolve_exclusions(defn, index)

    if provider_ctx and not on_ambiguous:
        provider, model_id = provider_ctx
        if defn.policy.ambiguous_branch == AmbiguousBranchPolicy.REVIEW:
            on_ambiguous = LlmAmbiguousHook(
                provider=provider,
                model_id=model_id,
                index=index,
                defn=defn,
                source_fingerprint=source_fingerprint,
            )
            if not llm_provenance:
                llm_provenance = LlmProvenance(
                    provider=provider.endpoint.provider,
                    model_id=model_id,
                    prompt_version="branch-v1",
                    schema_version="1",
                )

    traversal = traverse(
        index,
        root_res.resolved,
        explicit_ex,
        facet_ex,
        defn,
        on_ambiguous=on_ambiguous,
    )

    d_hash = domain_hash(defn)

    lock_resolved_roots = [
        LockResolvedRoot(
            query=r.query,
            resolved_category=r.category,
            max_depth=r.max_depth,
        )
        for r in root_res.resolved
    ]

    now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")

    raw_data = {
        "schema_version": 1,
        "domain_id": defn.id,
        "domain_hash": d_hash,
        "source_fingerprint": source_fingerprint,
        "resolved_roots": [r.model_dump(mode="json") for r in lock_resolved_roots],
        "category_decisions": [d.model_dump(mode="json") for d in traversal.decisions],
        "hard_exclude_pages": defn.hard_exclude_pages,
        "forced_include_pages": defn.forced_include_pages,
        "llm": llm_provenance.model_dump(mode="json") if llm_provenance else None,
        "compiler_version": __version__,
        "compiled_at": now_iso,
        "warnings_acknowledged": list(acknowledged_warnings),
    }

    calculated_lock_hash = DomainLock.compute_hash(raw_data)
    raw_data["lock_hash"] = calculated_lock_hash

    lock = DomainLock.model_validate(raw_data)
    return lock, traversal


def verify_lock(lock: DomainLock, defn: DomainDefinition, source_fingerprint: str) -> list[str]:
    """Verify DomainLock integrity and match against current domain definition and source."""
    errors: list[str] = []

    # 1. Lock hash calculation check
    data = lock.model_dump(mode="json")
    expected_hash = DomainLock.compute_hash(data)
    if lock.lock_hash != expected_hash:
        errors.append("tampered_lock_hash")

    # 2. Domain hash match check
    if lock.domain_hash != domain_hash(defn):
        errors.append("mismatched_domain_hash")

    # 3. Source fingerprint match check
    if lock.source_fingerprint != source_fingerprint:
        errors.append("mismatched_source_fingerprint")

    return errors


def write_lock(lock: DomainLock, path: Path | str) -> None:
    """Write DomainLock model to JSON file with sorted keys and trailing newline."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = lock.model_dump(mode="json")
    json_str = json.dumps(data, indent=2, sort_keys=True) + "\n"
    p.write_text(json_str, encoding="utf-8")


def read_lock(path: Path | str) -> DomainLock:
    """Read DomainLock model from JSON file."""
    p = Path(path).resolve()
    content = p.read_text(encoding="utf-8")
    data = json.loads(content)
    return DomainLock.model_validate(data)
