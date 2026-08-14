import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from corpussieve.contracts.enums import JobState
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode

ACTIVE_STATES = {
    JobState.METADATA_INDEXING,
    JobState.BUILDING,
    JobState.VALIDATING,
}

VALID_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.NEW: {
        JobState.SOURCE_INSPECTED,
        JobState.METADATA_INDEXING,
        JobState.DOMAIN_COMPILED,
        JobState.BUILDING,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.SOURCE_INSPECTED: {JobState.METADATA_INDEXING, JobState.FAILED, JobState.CANCELLED},
    JobState.METADATA_INDEXING: {JobState.METADATA_READY, JobState.FAILED, JobState.CANCELLED},
    JobState.METADATA_READY: {
        JobState.DOMAIN_DRAFT,
        JobState.DOMAIN_COMPILED,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.DOMAIN_DRAFT: {JobState.DOMAIN_COMPILED, JobState.FAILED, JobState.CANCELLED},
    JobState.DOMAIN_COMPILED: {
        JobState.PREVIEWED,
        JobState.BUILDING,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.PREVIEWED: {JobState.BUILDING, JobState.FAILED, JobState.CANCELLED},
    JobState.BUILDING: {JobState.BUILD_SUCCEEDED, JobState.FAILED, JobState.CANCELLED},
    JobState.BUILD_SUCCEEDED: {JobState.VALIDATING, JobState.FAILED, JobState.CANCELLED},
    JobState.VALIDATING: {JobState.VALIDATED, JobState.FAILED, JobState.CANCELLED},
    JobState.VALIDATED: {
        JobState.EXPORTED,
        JobState.SOURCE_PURGED,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.EXPORTED: {JobState.SOURCE_PURGED, JobState.FAILED, JobState.CANCELLED},
    JobState.SOURCE_PURGED: {JobState.FAILED, JobState.CANCELLED},
    JobState.FAILED: set(),
    JobState.CANCELLED: set(),
}


class JobStore:
    """SQLite job state machine persistence and checkpoint store."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()
        self._apply_crash_recovery()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if hasattr(self, "_conn") and self._conn:
            self._conn.close()

    def _init_tables(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    lock_hash TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    interrupted INTEGER DEFAULT 0
                )
            """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    job_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, seq)
                )
            """
            )

    def _apply_crash_recovery(self) -> None:
        """Crash Rule: Mark any active state job on open as interrupted=1."""
        now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        active_state_strs = [str(s) for s in ACTIVE_STATES]
        placeholders = ",".join("?" for _ in active_state_strs)
        with self._conn:
            self._conn.execute(
                f"""
                UPDATE jobs
                SET interrupted = 1, updated_at = ?
                WHERE state IN ({placeholders}) AND interrupted = 0
            """,
                [now_iso, *active_state_strs],
            )

    def create_job(self, kind: str, lock_hash: str | None = None) -> str:
        """Create new job in state NEW."""
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO jobs (job_id, kind, state, created_at, updated_at, lock_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (job_id, kind, str(JobState.NEW), now_iso, now_iso, lock_hash),
            )
        return job_id

    def transition(
        self,
        job_id: str,
        new_state: JobState,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Transition job to new state enforcing valid state transition graph."""
        cursor = self._conn.execute("SELECT state FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            raise CorpusSieveError(
                ErrorCode.INTERNAL_ERROR,
                f"Job '{job_id}' does not exist",
            )

        current_state = JobState(row["state"])
        valid_targets = VALID_TRANSITIONS.get(current_state, set())

        if new_state not in valid_targets:
            msg = f"Illegal transition from {current_state} to {new_state}"
            raise CorpusSieveError(ErrorCode.INTERNAL_ERROR, msg)

        now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        with self._conn:
            self._conn.execute(
                """
                UPDATE jobs
                SET state = ?, updated_at = ?, error_code = ?, error_message = ?, interrupted = 0
                WHERE job_id = ?
            """,
                (str(new_state), now_iso, error_code, error_message, job_id),
            )

    def save_checkpoint(self, job_id: str, payload: dict[str, Any]) -> int:
        """Save a checkpoint for job_id with payload dictionary and return sequence number."""
        cursor = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM checkpoints WHERE job_id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        next_seq: int = int(row["next_seq"]) if row and row["next_seq"] is not None else 1
        payload_json = json.dumps(payload, sort_keys=True)
        now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO checkpoints (job_id, seq, payload_json, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (job_id, next_seq, payload_json, now_iso),
            )
        return next_seq

    def latest_checkpoint(self, job_id: str) -> dict[str, Any] | None:
        """Return payload dictionary from latest checkpoint for job, or None."""
        cursor = self._conn.execute(
            "SELECT payload_json FROM checkpoints WHERE job_id = ? ORDER BY seq DESC LIMIT 1",
            (job_id,),
        )
        row = cursor.fetchone()
        if not row or not row["payload_json"]:
            return None
        res: dict[str, Any] = json.loads(row["payload_json"])
        return res

    def active_job(self, kind: str) -> dict[str, Any] | None:
        """Return active or interrupted job dictionary for kind, or None."""
        sql = (
            "SELECT * FROM jobs WHERE kind = ? AND "
            "(interrupted = 1 OR state IN ('BUILDING', 'METADATA_INDEXING', 'VALIDATING')) "
            "ORDER BY updated_at DESC LIMIT 1"
        )
        cursor = self._conn.execute(sql, (kind,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)
