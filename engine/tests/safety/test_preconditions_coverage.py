import json
import shutil
from pathlib import Path

from corpussieve.safety.preconditions import check_purge_preconditions
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"
EX_YAML = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "examples"
    / "domains"
    / "video-games.yaml"
)


def test_missing_state_db_blocks_purge(tmp_path: Path) -> None:
    proj_dir = tmp_path / "noproj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    plan, blockers = check_purge_preconditions(proj_dir)
    assert plan is None
    assert any(b.code == "PURGE_OUTPUT_UNVERIFIED" for b in blockers)


def test_missing_build_report_blocks_purge(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    state_db = proj_dir / "state.sqlite"

    from corpussieve.contracts.enums import JobState
    from corpussieve.jobs.state import JobStore

    with JobStore(state_db) as store:
        j_id = store.create_job("build")
        store.transition(j_id, JobState.BUILDING)
        store.transition(j_id, JobState.BUILD_SUCCEEDED)
        store.transition(j_id, JobState.VALIDATING)
        store.transition(j_id, JobState.VALIDATED)

    plan, blockers = check_purge_preconditions(proj_dir)
    assert plan is None
    assert any(b.code == "PURGE_OUTPUT_UNVERIFIED" and "report" in b.message for b in blockers)


def test_missing_source_dir_blocks_purge(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    state_db = proj_dir / "state.sqlite"

    from corpussieve.contracts.enums import JobState
    from corpussieve.jobs.state import JobStore

    with JobStore(state_db) as store:
        j_id = store.create_job("build")
        store.transition(j_id, JobState.BUILDING)
        store.transition(j_id, JobState.BUILD_SUCCEEDED)
        store.transition(j_id, JobState.VALIDATING)
        store.transition(j_id, JobState.VALIDATED)

    out_corpus = proj_dir / "output" / "corpus"
    out_corpus.mkdir(parents=True, exist_ok=True)
    report_file = out_corpus / "build-report.json"
    report_file.write_text(json.dumps({"validation": "PASSED"}), encoding="utf-8")

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_corpus)
    assert plan is None
    assert any(b.code == "PURGE_SOURCE_CHANGED" for b in blockers)


def test_missing_lock_file_blocks_purge(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    source_dir = proj_dir / "source"
    shutil.copytree(FIXWIKI_DIR, source_dir)

    adapter = WikimediaXmlDumpAdapter(source_dir)
    fp = adapter.fingerprint().fingerprint

    state_db = proj_dir / "state.sqlite"

    from corpussieve.contracts.enums import JobState
    from corpussieve.jobs.state import JobStore

    with JobStore(state_db) as store:
        j_id = store.create_job("build")
        store.transition(j_id, JobState.BUILDING)
        store.transition(j_id, JobState.BUILD_SUCCEEDED)
        store.transition(j_id, JobState.VALIDATING)
        store.transition(j_id, JobState.VALIDATED)

    out_corpus = proj_dir / "output" / "corpus"
    out_corpus.mkdir(parents=True, exist_ok=True)
    report_file = out_corpus / "build-report.json"
    rep_json = json.dumps({"validation": "PASSED", "source_fingerprint": fp})
    report_file.write_text(rep_json, encoding="utf-8")

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_corpus)
    assert plan is None
    assert any("Domain lockfile does not exist" in b.message for b in blockers)


def test_corpus_revalidation_failed_blocks_purge(tmp_path: Path) -> None:
    from tests.safety.test_destructive_invariants import _setup_project

    proj_dir, out_dir, _source_dir = _setup_project(tmp_path)

    # Tamper corpus file (truncate it) to cause validate_corpus re-validation to fail
    corpus_file = out_dir / "corpus" / "corpus.jsonl.zst"
    corpus_file.write_bytes(b"invalid zstd header")

    plan, blockers = check_purge_preconditions(proj_dir, output_dir=out_dir / "corpus")
    assert plan is None
    assert any("Canonical corpus re-validation failed" in b.message for b in blockers)


def test_invalid_job_state_blocks_purge(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    state_db = proj_dir / "state.sqlite"

    from corpussieve.contracts.enums import JobState
    from corpussieve.jobs.state import JobStore

    with JobStore(state_db) as store:
        j_id = store.create_job("build")
        store.transition(j_id, JobState.BUILDING)

    plan, blockers = check_purge_preconditions(proj_dir)
    assert plan is None
    assert any("Build job state is not VALIDATED or EXPORTED" in b.message for b in blockers)
