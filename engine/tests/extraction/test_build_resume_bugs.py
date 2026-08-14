import shutil
from pathlib import Path

import pytest
import yaml

from corpussieve.contracts.enums import JobState
from corpussieve.contracts.errors import CorpusSieveError
from corpussieve.domain.definition import load_domain
from corpussieve.domain.lock_build import compile_lock, write_lock
from corpussieve.extraction.build import run_build
from corpussieve.jobs.state import JobStore
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"
EX_YAML = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "examples"
    / "domains"
    / "video-games.yaml"
)


def test_build_uses_project_yaml_source_paths(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    out_dir = tmp_path / "fixoutput"
    custom_dumps_dir = tmp_path / "custom_dumps"
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXWIKI_DIR, custom_dumps_dir)

    adapter = WikimediaXmlDumpAdapter(custom_dumps_dir)
    build_metadata_index(adapter, proj_dir / "cache" / "metadata.sqlite")

    shutil.copy(EX_YAML, proj_dir / "domain.yaml")
    defn = load_domain(proj_dir / "domain.yaml")
    with MetadataIndex(proj_dir / "cache" / "metadata.sqlite") as idx:
        stats = idx.stats()
        lock, _ = compile_lock(defn, idx, stats.source_fingerprint)
        lock_path = proj_dir / "domain.lock.json"
        write_lock(lock, lock_path)

    project_yaml = proj_dir / "project.yaml"
    p_data = {
        "schema_version": 1,
        "project_id": "test_proj",
        "name": "test_proj",
        "created_at": "2026-08-01T00:00:00Z",
        "source_paths": [str(custom_dumps_dir)],
        "source_adapter": "WikimediaXmlDumpAdapter",
        "domain_path": str(proj_dir / "domain.yaml"),
        "lock_path": str(lock_path),
        "output_dir": str(out_dir),
        "job_state": "NEW",
    }
    project_yaml.write_text(yaml.dump(p_data), encoding="utf-8")

    # proj_dir / "source" does NOT exist, but build should succeed using project.yaml source_paths
    report = run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)
    assert report.validation == "PASSED"
    assert (out_dir / "corpus" / "corpus.jsonl.zst").exists()


def test_build_failure_transitions_job_to_failed_and_resume(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    out_dir = tmp_path / "fixoutput"
    custom_dumps_dir = tmp_path / "custom_dumps"
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXWIKI_DIR, custom_dumps_dir)

    adapter = WikimediaXmlDumpAdapter(custom_dumps_dir)
    build_metadata_index(adapter, proj_dir / "cache" / "metadata.sqlite")

    shutil.copy(EX_YAML, proj_dir / "domain.yaml")
    defn = load_domain(proj_dir / "domain.yaml")
    with MetadataIndex(proj_dir / "cache" / "metadata.sqlite") as idx:
        stats = idx.stats()
        lock, _ = compile_lock(defn, idx, stats.source_fingerprint)
        lock_path = proj_dir / "domain.lock.json"
        write_lock(lock, lock_path)

    project_yaml = proj_dir / "project.yaml"
    p_data = {
        "schema_version": 1,
        "project_id": "test_proj",
        "name": "test_proj",
        "created_at": "2026-08-01T00:00:00Z",
        "source_paths": [str(tmp_path / "non_existent_source_dir")],
        "source_adapter": "WikimediaXmlDumpAdapter",
        "domain_path": str(proj_dir / "domain.yaml"),
        "lock_path": str(lock_path),
        "output_dir": str(out_dir),
        "job_state": "NEW",
    }
    project_yaml.write_text(yaml.dump(p_data), encoding="utf-8")

    # Run build with non-existent source directory -> throws CorpusSieveError
    with pytest.raises(CorpusSieveError):
        run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)

    state_db = proj_dir / "state.sqlite"
    assert state_db.exists()
    with JobStore(state_db) as store:
        job = store.latest_job("build")
        assert job is not None
        assert job["state"] == JobState.FAILED.value or job["state"] == "FAILED"

    # Now fix project.yaml source_paths and resume build
    p_data["source_paths"] = [str(custom_dumps_dir)]
    project_yaml.write_text(yaml.dump(p_data), encoding="utf-8")

    report = run_build(
        proj_dir, lock_path, out_dir, allow_low_disk=True, resume_job_id=job["job_id"]
    )
    assert report.validation == "PASSED"


def test_build_resolves_source_relative_to_project_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proj_dir = tmp_path / "fixproj"
    out_dir = tmp_path / "fixoutput"
    rel_dumps_name = "rel_dumps"
    rel_dumps_dir = proj_dir / rel_dumps_name
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXWIKI_DIR, rel_dumps_dir)

    adapter = WikimediaXmlDumpAdapter(rel_dumps_dir)
    build_metadata_index(adapter, proj_dir / "cache" / "metadata.sqlite")

    shutil.copy(EX_YAML, proj_dir / "domain.yaml")
    defn = load_domain(proj_dir / "domain.yaml")
    with MetadataIndex(proj_dir / "cache" / "metadata.sqlite") as idx:
        stats = idx.stats()
        lock, _ = compile_lock(defn, idx, stats.source_fingerprint)
        lock_path = proj_dir / "domain.lock.json"
        write_lock(lock, lock_path)

    project_yaml = proj_dir / "project.yaml"
    p_data = {
        "schema_version": 1,
        "project_id": "test_proj",
        "name": "test_proj",
        "created_at": "2026-08-01T00:00:00Z",
        "source_paths": [rel_dumps_name],  # Relative path!
        "source_adapter": "WikimediaXmlDumpAdapter",
        "domain_path": str(proj_dir / "domain.yaml"),
        "lock_path": str(lock_path),
        "output_dir": str(out_dir),
        "job_state": "NEW",
    }
    project_yaml.write_text(yaml.dump(p_data), encoding="utf-8")

    # Change current working directory to somewhere else completely
    other_dir = tmp_path / "other_cwd"
    other_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(other_dir)

    # Build should resolve rel_dumps_name relative to proj_dir, not process CWD
    report = run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)
    assert report.validation == "PASSED"
    assert (out_dir / "corpus" / "corpus.jsonl.zst").exists()
