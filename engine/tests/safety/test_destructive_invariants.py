import hashlib
import shutil
from pathlib import Path

import pytest

from corpussieve.contracts.errors import CorpusSieveError
from corpussieve.extraction.build import run_build
from corpussieve.metadata.build import build_metadata_index
from corpussieve.safety.preconditions import check_purge_preconditions
from corpussieve.safety.purge import execute_purge
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def _dir_hash(directory: Path) -> str:
    hasher = hashlib.sha256()
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            hasher.update(p.relative_to(directory).as_posix().encode("utf-8"))
            hasher.update(p.read_bytes())
    return hasher.hexdigest()


def test_build_never_deletes_source(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    out_dir = tmp_path / "fixoutput"
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_dir = proj_dir / "source"
    shutil.copytree(FIXWIKI_DIR, source_dir)
    before_hash = _dir_hash(source_dir)

    adapter = WikimediaXmlDumpAdapter(source_dir)
    build_metadata_index(adapter, proj_dir / "cache" / "metadata.sqlite")

    # Copy domain lock
    shutil.copytree(
        Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki",
        proj_dir / "domains",
        dirs_exist_ok=True,
    )
    domain_file = proj_dir / "domains" / "video-games.yaml"
    ex_yaml = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "examples"
        / "domains"
        / "video-games.yaml"
    )
    if not domain_file.exists():
        shutil.copy(ex_yaml, proj_dir / "domain.yaml")
        domain_file = proj_dir / "domain.yaml"

    from corpussieve.domain.definition import load_domain
    from corpussieve.domain.lock_build import compile_lock, write_lock

    defn = load_domain(domain_file)

    from corpussieve.metadata.queries import MetadataIndex

    with MetadataIndex(proj_dir / "cache" / "metadata.sqlite") as idx:
        stats = idx.stats()
        lock, _ = compile_lock(defn, idx, stats.source_fingerprint)
        lock_path = proj_dir / "domain.lock.json"
        write_lock(lock, lock_path)

    run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)

    after_hash = _dir_hash(source_dir)
    assert before_hash == after_hash


def test_changed_source_blocks_purge(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    out_dir = tmp_path / "fixoutput"
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_dir = proj_dir / "source"
    shutil.copytree(FIXWIKI_DIR, source_dir)

    adapter = WikimediaXmlDumpAdapter(source_dir)
    build_metadata_index(adapter, proj_dir / "cache" / "metadata.sqlite")

    ex_yaml = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "examples"
        / "domains"
        / "video-games.yaml"
    )
    shutil.copy(ex_yaml, proj_dir / "domain.yaml")
    from corpussieve.domain.definition import load_domain
    from corpussieve.domain.lock_build import compile_lock, write_lock
    from corpussieve.metadata.queries import MetadataIndex

    defn = load_domain(proj_dir / "domain.yaml")
    with MetadataIndex(proj_dir / "cache" / "metadata.sqlite") as idx:
        stats = idx.stats()
        lock, _ = compile_lock(defn, idx, stats.source_fingerprint)
        lock_path = proj_dir / "domain.lock.json"
        write_lock(lock, lock_path)

    run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)

    # Modify an existing source dump file after build
    dump_files = [f for f in source_dir.iterdir() if f.is_file()]
    assert dump_files, "Expected dump files in source_dir"
    dump_files[0].write_bytes(b"tampered content")

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_dir / "corpus")
    assert plan is None
    assert any(b.code == "PURGE_SOURCE_CHANGED" for b in blockers)


def test_wrong_confirm_token_rejected(tmp_path: Path) -> None:
    proj_dir = tmp_path / "myproject"
    out_dir = tmp_path / "fixoutput"
    proj_dir.mkdir(parents=True, exist_ok=True)

    source_dir = proj_dir / "source"
    shutil.copytree(FIXWIKI_DIR, source_dir)

    adapter = WikimediaXmlDumpAdapter(source_dir)
    build_metadata_index(adapter, proj_dir / "cache" / "metadata.sqlite")

    ex_yaml = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "examples"
        / "domains"
        / "video-games.yaml"
    )
    shutil.copy(ex_yaml, proj_dir / "domain.yaml")
    from corpussieve.domain.definition import load_domain
    from corpussieve.domain.lock_build import compile_lock, write_lock
    from corpussieve.metadata.queries import MetadataIndex

    defn = load_domain(proj_dir / "domain.yaml")
    with MetadataIndex(proj_dir / "cache" / "metadata.sqlite") as idx:
        stats = idx.stats()
        lock, _ = compile_lock(defn, idx, stats.source_fingerprint)
        lock_path = proj_dir / "domain.lock.json"
        write_lock(lock, lock_path)

    run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_dir / "corpus")
    assert plan is not None

    with pytest.raises(CorpusSieveError):
        execute_purge(plan, mode="permanent", confirm_token="wrong_project_name")
