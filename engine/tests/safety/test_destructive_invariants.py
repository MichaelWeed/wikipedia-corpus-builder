import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from corpussieve.contracts.errors import CorpusSieveError
from corpussieve.domain.definition import load_domain
from corpussieve.domain.lock_build import compile_lock, write_lock
from corpussieve.extraction.build import run_build
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.safety.preconditions import check_purge_preconditions
from corpussieve.safety.purge import execute_purge
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"
EX_YAML = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "examples"
    / "domains"
    / "video-games.yaml"
)


def _dir_hash(directory: Path) -> str:
    hasher = hashlib.sha256()
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            hasher.update(p.relative_to(directory).as_posix().encode("utf-8"))
            hasher.update(p.read_bytes())
    return hasher.hexdigest()


def _setup_project(
    tmp_path: Path, proj_name: str = "fixproj", out_name: str = "fixoutput"
) -> tuple[Path, Path, Path]:
    proj_dir = tmp_path / proj_name
    out_dir = tmp_path / out_name
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_dir = proj_dir / "source"
    shutil.copytree(FIXWIKI_DIR, source_dir)

    adapter = WikimediaXmlDumpAdapter(source_dir)
    build_metadata_index(adapter, proj_dir / "cache" / "metadata.sqlite")

    shutil.copy(EX_YAML, proj_dir / "domain.yaml")
    defn = load_domain(proj_dir / "domain.yaml")
    with MetadataIndex(proj_dir / "cache" / "metadata.sqlite") as idx:
        stats = idx.stats()
        lock, _ = compile_lock(defn, idx, stats.source_fingerprint)
        lock_path = proj_dir / "domain.lock.json"
        write_lock(lock, lock_path)

    run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)
    return proj_dir, out_dir, source_dir


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

    shutil.copy(EX_YAML, proj_dir / "domain.yaml")
    defn = load_domain(proj_dir / "domain.yaml")
    with MetadataIndex(proj_dir / "cache" / "metadata.sqlite") as idx:
        stats = idx.stats()
        lock, _ = compile_lock(defn, idx, stats.source_fingerprint)
        lock_path = proj_dir / "domain.lock.json"
        write_lock(lock, lock_path)

    run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)

    after_hash = _dir_hash(source_dir)
    assert before_hash == after_hash


def test_changed_source_blocks_purge(tmp_path: Path) -> None:
    proj_dir, out_dir, source_dir = _setup_project(tmp_path)

    # Modify an existing source dump file after build
    dump_files = [f for f in source_dir.iterdir() if f.is_file()]
    assert dump_files, "Expected dump files in source_dir"
    dump_files[0].write_bytes(b"tampered content")

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_dir / "corpus")
    assert plan is None
    assert any(b.code == "PURGE_SOURCE_CHANGED" for b in blockers)


def test_wrong_confirm_token_rejected(tmp_path: Path) -> None:
    proj_dir, out_dir, _source_dir = _setup_project(tmp_path, proj_name="myproject")

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_dir / "corpus")
    assert plan is not None
    assert not blockers

    with pytest.raises(CorpusSieveError):
        execute_purge(plan, mode="permanent", confirm_token="wrong_project_name")


def test_failed_validation_blocks_purge(tmp_path: Path) -> None:
    proj_dir, out_dir, _source_dir = _setup_project(tmp_path)

    # Doctor build-report.json to set validation state to FAILED
    report_file = out_dir / "corpus" / "build-report.json"
    rep_data = json.loads(report_file.read_text(encoding="utf-8"))
    rep_data["validation"] = "FAILED"
    report_file.write_text(json.dumps(rep_data), encoding="utf-8")

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_dir / "corpus")
    assert plan is None
    assert any(b.code == "PURGE_OUTPUT_UNVERIFIED" for b in blockers)


def test_output_inside_delete_target_blocks_purge(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    source_dir = proj_dir / "source"
    shutil.copytree(FIXWIKI_DIR, source_dir)

    out_dir = source_dir / "output_nested"
    out_dir.mkdir(parents=True, exist_ok=True)

    adapter = WikimediaXmlDumpAdapter(source_dir)
    build_metadata_index(adapter, proj_dir / "cache" / "metadata.sqlite")

    shutil.copy(EX_YAML, proj_dir / "domain.yaml")
    defn = load_domain(proj_dir / "domain.yaml")
    with MetadataIndex(proj_dir / "cache" / "metadata.sqlite") as idx:
        stats = idx.stats()
        lock, _ = compile_lock(defn, idx, stats.source_fingerprint)
        lock_path = proj_dir / "domain.lock.json"
        write_lock(lock, lock_path)

    run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_dir / "corpus")
    assert plan is None
    assert any(b.code == "output_inside_target" for b in blockers)


def test_symlink_canonicalization_cannot_escape_scope(tmp_path: Path) -> None:
    proj_dir, out_dir, source_dir = _setup_project(tmp_path)

    # Create hostile symlink inside source pointing outside
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret outside content", encoding="utf-8")

    symlink_file = source_dir / "hostile_link.txt"
    try:
        os.symlink(outside_file, symlink_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform/user environment")

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_dir / "corpus")
    assert plan is None
    assert any(b.code == "symlink_escape_scope" for b in blockers)


def test_purge_removes_only_planned_files(tmp_path: Path) -> None:
    proj_dir, out_dir, source_dir = _setup_project(tmp_path, proj_name="purgeme")

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_dir / "corpus")
    assert plan is not None
    assert not blockers

    # Check files to delete are all inside source_dir
    for f in plan.files_to_delete:
        assert Path(f).is_relative_to(source_dir)

    result = execute_purge(plan, mode="permanent", confirm_token="purgeme")
    assert result.status == "SUCCESS"

    # Source dump files are deleted
    for f in plan.files_to_delete:
        assert not Path(f).exists()

    # Corpus directory and report files remain untouched
    assert (out_dir / "corpus" / "corpus.jsonl.zst").exists()
    assert (out_dir / "corpus" / "build-report.json").exists()
