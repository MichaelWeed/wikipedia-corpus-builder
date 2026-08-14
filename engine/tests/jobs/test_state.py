from pathlib import Path

import pytest

from corpussieve.contracts.enums import JobState
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.jobs.state import JobStore


def test_job_store_legal_transitions(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    with JobStore(db_path) as store:
        job_id = store.create_job("build")
        store.transition(job_id, JobState.SOURCE_INSPECTED)
        store.transition(job_id, JobState.METADATA_INDEXING)
        store.transition(job_id, JobState.METADATA_READY)
        store.transition(job_id, JobState.DOMAIN_COMPILED)
        store.transition(job_id, JobState.BUILDING)
        store.transition(job_id, JobState.BUILD_SUCCEEDED)
        store.transition(job_id, JobState.VALIDATING)
        store.transition(job_id, JobState.VALIDATED)


def test_job_store_illegal_transition(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    with JobStore(db_path) as store:
        job_id = store.create_job("build")
        with pytest.raises(CorpusSieveError) as exc_info:
            store.transition(job_id, JobState.VALIDATED)
        assert exc_info.value.code == ErrorCode.INTERNAL_ERROR


def test_job_store_checkpoint(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    with JobStore(db_path) as store:
        job_id = store.create_job("build")
        seq1 = store.save_checkpoint(job_id, {"completed_offsets": [100, 200]})
        seq2 = store.save_checkpoint(job_id, {"completed_offsets": [100, 200, 300]})
        assert seq1 == 1
        assert seq2 == 2

        latest = store.latest_checkpoint(job_id)
        assert latest is not None
        assert latest["completed_offsets"] == [100, 200, 300]


def test_job_store_crash_recovery(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    with JobStore(db_path) as store:
        job_id = store.create_job("build")
        store.transition(job_id, JobState.SOURCE_INSPECTED)
        store.transition(job_id, JobState.METADATA_INDEXING)

    # Re-open store to simulate crash recovery
    with JobStore(db_path) as store2:
        act = store2.active_job("build")
        assert act is not None
        assert act["job_id"] == job_id
        assert act["interrupted"] == 1
