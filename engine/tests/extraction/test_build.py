import shutil
from pathlib import Path

import pytest

from corpussieve.contracts.domain import DomainDefinition, DomainRoot
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.domain.definition import save_domain
from corpussieve.domain.lock_build import compile_lock, write_lock
from corpussieve.extraction.build import run_build
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_end_to_end_fixwiki_build(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    out_dir = tmp_path / "fixoutput"
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy source fixture into proj_dir/source
    source_dir = proj_dir / "source"
    shutil.copytree(FIXWIKI_DIR, source_dir)

    # 2. Build metadata index
    adapter = WikimediaXmlDumpAdapter(source_dir)
    db_path = proj_dir / "cache" / "metadata.sqlite"
    build_metadata_index(adapter, db_path)

    # 3. Create domain & compile lock
    idx = MetadataIndex(db_path)
    fp = adapter.inspect().fingerprint.fingerprint
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )
    save_domain(defn, proj_dir / "domain.yaml")
    lock, _ = compile_lock(defn, idx, fp)
    lock_path = proj_dir / "domain.lock.json"
    write_lock(lock, lock_path)

    # 4. Run build
    report = run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)
    assert report.validation == "PASSED"
    assert report.extraction_count > 0
    assert (out_dir / "corpus" / "corpus.jsonl.zst").exists()
    assert (out_dir / "corpus" / "build-report.json").exists()


def test_build_disk_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    proj_dir = tmp_path / "fixproj"
    out_dir = tmp_path / "fixoutput"
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_dir = proj_dir / "source"
    shutil.copytree(FIXWIKI_DIR, source_dir)

    adapter = WikimediaXmlDumpAdapter(source_dir)
    db_path = proj_dir / "cache" / "metadata.sqlite"
    build_metadata_index(adapter, db_path)

    idx = MetadataIndex(db_path)
    fp = adapter.inspect().fingerprint.fingerprint
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )
    save_domain(defn, proj_dir / "domain.yaml")
    lock, _ = compile_lock(defn, idx, fp)
    lock_path = proj_dir / "domain.lock.json"
    write_lock(lock, lock_path)

    # Mock disk_usage returning 100 bytes free space
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: (1000, 900, 100))

    with pytest.raises(CorpusSieveError) as exc_info:
        run_build(proj_dir, lock_path, out_dir, allow_low_disk=False)
    assert exc_info.value.code == ErrorCode.OUTPUT_DISK_INSUFFICIENT
