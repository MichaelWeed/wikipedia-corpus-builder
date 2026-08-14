import pytest
from pydantic import ValidationError

from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.enums import BranchDecision
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.hashing import canonical_json_hash
from corpussieve.contracts.llm_io import BranchReviewResult
from corpussieve.contracts.lock import DomainLock
from corpussieve.contracts.project import ProjectFile


def test_canonical_json_hash_stability() -> None:
    data = {"b": 2, "a": 1, "nested": {"y": "val", "x": 100}}
    # Digest of {"a":1,"b":2,"nested":{"x":100,"y":"val"}}
    digest = canonical_json_hash(data)
    assert digest == "9fcb04c03b983ef70bb89d6cf1c6ab6132a9986f09ffc42f1544da4e23f1252b"


def test_domain_definition_valid_and_rejection() -> None:
    valid_data = {
        "schema_version": 1,
        "id": "video-games",
        "name": "Video Games",
        "description": "Video games topic domain",
        "language": "en",
        "policy": {"mode": "balanced"},
        "roots": [{"query": "Category:Video games", "max_depth": 4}],
    }
    dom = DomainDefinition.model_validate(valid_data)
    assert dom.id == "video-games"

    # Reject invalid slug
    with pytest.raises(ValidationError):
        DomainDefinition.model_validate({**valid_data, "id": "Invalid Slug!"})

    # Reject unknown extra field
    with pytest.raises(ValidationError):
        DomainDefinition.model_validate({**valid_data, "unknown_field": "invalid"})


def test_branch_review_confidence_range() -> None:
    valid = BranchReviewResult(
        decision=BranchDecision.INCLUDE,
        confidence=0.85,
        reason="Relevant game subcategory",
        needs_human_review=False,
    )
    assert valid.confidence == 0.85

    with pytest.raises(ValidationError):
        BranchReviewResult(
            decision=BranchDecision.INCLUDE,
            confidence=1.5,  # Out of range 0..1
            reason="Invalid",
            needs_human_review=False,
        )


def test_domain_lock_hash_excludes_itself() -> None:
    raw_lock = {
        "schema_version": 1,
        "domain_id": "video-games",
        "domain_hash": "abc123hash",
        "source_fingerprint": "srcfp123",
        "resolved_roots": [
            {
                "query": "Category:Video games",
                "resolved_category": "Category:Video_games",
                "max_depth": 4,
            }
        ],
        "category_decisions": [
            {
                "category": "Category:Video_games",
                "decision": "include",
                "source": "traversal",
                "reason": "root",
            }
        ],
        "compiler_version": "0.1.0",
        "compiled_at": "2026-08-13T00:00:00Z",
        "lock_hash": "placeholder",
    }
    computed_hash = DomainLock.compute_hash(raw_lock)
    lock_obj = DomainLock.model_validate({**raw_lock, "lock_hash": computed_hash})
    assert lock_obj.lock_hash == computed_hash


def test_project_file_no_secrets() -> None:
    valid_proj = ProjectFile(
        project_id="p1",
        name="Test Project",
        created_at="2026-08-13T00:00:00Z",
        source_paths=["/path/to/dump.xml"],
        source_adapter="wikimedia_xml_dump",
        domain_path="domain.yaml",
        lock_path="domain.lock.json",
        output_dir="dist",
        provider_ref="keyring://ollama/local",
    )
    assert valid_proj.project_id == "p1"

    with pytest.raises(ValidationError):
        ProjectFile(
            project_id="p2",
            name="Bad Secret Project",
            created_at="2026-08-13T00:00:00Z",
            source_paths=["/path/to/dump.xml"],
            source_adapter="wikimedia_xml_dump",
            domain_path="domain.yaml",
            lock_path="domain.lock.json",
            output_dir="dist",
            provider_ref="sk-1234567890abcdef1234567890abcdef",  # forbidden token format
        )


def test_corpus_sieve_error() -> None:
    err = CorpusSieveError(ErrorCode.SOURCE_UNSUPPORTED, "Unsupported format", {"format": "rar"})
    assert err.code == ErrorCode.SOURCE_UNSUPPORTED
    assert str(err) == "Unsupported format"
    assert err.detail == {"format": "rar"}
