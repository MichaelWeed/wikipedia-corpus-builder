from pathlib import Path

import pytest

from corpussieve.contracts.domain import DomainDefinition, DomainRoot
from corpussieve.domain.lock_build import (
    compile_lock,
    read_lock,
    verify_lock,
    write_lock,
)
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


@pytest.fixture
def fixwiki_idx(tmp_path: Path) -> tuple[MetadataIndex, str]:
    db_path = tmp_path / "cache" / "metadata.sqlite"
    adapter = WikimediaXmlDumpAdapter(FIXWIKI_DIR)
    build_metadata_index(adapter, db_path)
    fp = adapter.inspect().fingerprint.fingerprint
    return MetadataIndex(db_path), fp


def test_compile_lock_determinism(fixwiki_idx: tuple[MetadataIndex, str]) -> None:
    idx, fp = fixwiki_idx
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )

    lock1, _ = compile_lock(defn, idx, fp)
    lock2, _ = compile_lock(defn, idx, fp)

    # lock_hash should be identical except compiled_at timestamp difference
    assert lock1.domain_hash == lock2.domain_hash
    assert len(lock1.category_decisions) == len(lock2.category_decisions)


def test_verify_lock_success(fixwiki_idx: tuple[MetadataIndex, str]) -> None:
    idx, fp = fixwiki_idx
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )

    lock, _ = compile_lock(defn, idx, fp)
    errors = verify_lock(lock, defn, fp)
    assert errors == []


def test_verify_lock_tamper_detection(fixwiki_idx: tuple[MetadataIndex, str]) -> None:
    idx, fp = fixwiki_idx
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )

    lock, _ = compile_lock(defn, idx, fp)

    # 1. Tamper source fingerprint
    errors_fp = verify_lock(lock, defn, "wrong_fingerprint_123")
    assert "mismatched_source_fingerprint" in errors_fp

    # 2. Tamper definition
    defn_altered = DomainDefinition(
        id="vg",
        name="Video Games Altered",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )
    errors_defn = verify_lock(lock, defn_altered, fp)
    assert "mismatched_domain_hash" in errors_defn


def test_lock_write_read_round_trip(tmp_path: Path, fixwiki_idx: tuple[MetadataIndex, str]) -> None:
    idx, fp = fixwiki_idx
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )

    lock, _ = compile_lock(defn, idx, fp)
    lock_file = tmp_path / "domain.lock.json"

    write_lock(lock, lock_file)
    assert lock_file.exists()

    loaded = read_lock(lock_file)
    assert loaded.domain_id == lock.domain_id
    assert loaded.lock_hash == lock.lock_hash
