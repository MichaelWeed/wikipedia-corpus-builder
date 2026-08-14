import shutil
import threading
from pathlib import Path

import pytest

from corpussieve.contracts.domain import DomainDefinition, DomainRoot
from corpussieve.contracts.enums import JobState
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.events import ProgressEvent
from corpussieve.domain.definition import save_domain
from corpussieve.domain.lock_build import compile_lock, write_lock
from corpussieve.extraction.build import run_build
from corpussieve.jobs.events import EventBus
from corpussieve.jobs.state import JobStore
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def _setup_fixwiki_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Copy the fixwiki fixture into a fresh project dir and compile a lock.

    Returns (proj_dir, out_dir, lock_path).
    """
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
    return proj_dir, out_dir, lock_path


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


def test_run_build_reports_job_id_before_finishing(tmp_path: Path) -> None:
    """on_job_started must fire with the real job_id early enough that a
    caller (server.py's build.start) can register a cancel handle for it
    before the build finishes — not just after the fact."""
    proj_dir, out_dir, lock_path = _setup_fixwiki_project(tmp_path)

    seen_job_ids: list[str] = []
    report = run_build(
        proj_dir,
        lock_path,
        out_dir,
        allow_low_disk=True,
        on_job_started=seen_job_ids.append,
    )
    assert len(seen_job_ids) == 1
    assert seen_job_ids[0]
    assert report.validation == "PASSED"

    store = JobStore(proj_dir / "state.sqlite")
    row = store.get_job(seen_job_ids[0])
    store.close()
    assert row is not None
    assert row["state"] == str(JobState.VALIDATED)


def test_run_build_publishes_progress_events(tmp_path: Path) -> None:
    proj_dir, out_dir, lock_path = _setup_fixwiki_project(tmp_path)

    events: list[ProgressEvent] = []
    bus = EventBus()
    bus.subscribe(events.append)

    report = run_build(proj_dir, lock_path, out_dir, allow_low_disk=True, events=bus)

    assert report.validation == "PASSED"
    assert len(events) >= 2
    stages = [e.stage for e in events]
    assert str(JobState.BUILDING) in stages
    assert str(JobState.VALIDATED) in stages
    # completed_units should be monotonically non-decreasing across the run
    completed = [e.completed_units for e in events]
    assert completed == sorted(completed)
    for evt in events:
        assert evt.job_id
        assert evt.total_units == report.extraction_count or evt.total_units is not None


def test_run_build_cancellation_stops_extraction_and_cleans_up(tmp_path: Path) -> None:
    """A cancel_event set as soon as the job starts must stop the extraction
    loop, transition the job to CANCELLED (not FAILED — see the guard in
    build.py's except block), remove the staging dir, and publish a
    CANCELLED progress event instead of a FAILED one."""
    proj_dir, out_dir, lock_path = _setup_fixwiki_project(tmp_path)

    cancel_event = threading.Event()
    events: list[ProgressEvent] = []
    bus = EventBus()

    def _on_event(evt: ProgressEvent) -> None:
        events.append(evt)
        # Cancel as soon as the first ("starting extraction") event arrives,
        # so cancellation is guaranteed to land before any page is written.
        if evt.stage == str(JobState.BUILDING) and evt.completed_units == 0:
            cancel_event.set()

    bus.subscribe(_on_event)

    job_ids: list[str] = []
    with pytest.raises(CorpusSieveError) as exc_info:
        run_build(
            proj_dir,
            lock_path,
            out_dir,
            allow_low_disk=True,
            cancel_event=cancel_event,
            events=bus,
            on_job_started=job_ids.append,
        )
    assert "cancelled" in exc_info.value.message.lower()

    job_id = job_ids[0]
    store = JobStore(proj_dir / "state.sqlite")
    row = store.get_job(job_id)
    store.close()
    assert row is not None
    assert row["state"] == str(JobState.CANCELLED)
    assert row["state"] != str(JobState.FAILED)

    staging_dir = out_dir / f".staging-{job_id}"
    assert not staging_dir.exists()
    assert not (out_dir / "corpus").exists()

    cancelled_events = [e for e in events if e.stage == str(JobState.CANCELLED)]
    assert len(cancelled_events) == 1
    failed_events = [e for e in events if e.stage == str(JobState.FAILED)]
    assert failed_events == []
