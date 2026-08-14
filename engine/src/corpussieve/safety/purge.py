import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

try:
    import send2trash  # type: ignore[import-untyped]

    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False

from corpussieve.contracts.enums import JobState
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.jobs.state import JobStore
from corpussieve.safety.preconditions import PurgePlan, check_purge_preconditions


class PurgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCESS", "FAILED"]
    mode: Literal["trash", "permanent"]
    removed_files_count: int
    freed_bytes: int
    retained_corpus_path: str
    purged_at: str


def execute_purge(
    plan: PurgePlan,
    mode: Literal["trash", "permanent"],
    confirm_token: str,
) -> PurgeResult:
    """Execute safe purge of source dump files after mandatory preconditions check."""
    p_dir = Path(plan.project_dir).resolve()

    # 1. Typed confirmation check
    if confirm_token != plan.project_name:
        msg = f"Invalid token '{confirm_token}' (expected '{plan.project_name}')."
        raise CorpusSieveError(
            ErrorCode.INTERNAL_ERROR,
            msg,
        )

    # 2. TOCTOU re-check preconditions immediately before execution
    fresh_plan, blockers = check_purge_preconditions(p_dir, output_dir=plan.corpus_path)
    if blockers or not fresh_plan:
        blocker_msgs = ", ".join(b.message for b in blockers)
        raise CorpusSieveError(
            ErrorCode.PURGE_OUTPUT_UNVERIFIED,
            f"Purge preconditions check failed prior to execution: {blocker_msgs}",
        )

    removed_count = 0
    freed_bytes = 0

    for file_str in fresh_plan.files_to_delete:
        f_path = Path(file_str).resolve()
        if f_path.exists():
            size = f_path.stat().st_size
            if mode == "trash" and HAS_SEND2TRASH:
                send2trash.send2trash(str(f_path))
            else:
                f_path.unlink()
            removed_count += 1
            freed_bytes += size

    now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    result = PurgeResult(
        status="SUCCESS",
        mode=mode,
        removed_files_count=removed_count,
        freed_bytes=freed_bytes,
        retained_corpus_path=plan.corpus_path,
        purged_at=now_iso,
    )

    # Record purge report
    ts_str = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    purge_report_path = p_dir / "reports" / f"purge-{ts_str}.json"
    purge_report_path.parent.mkdir(parents=True, exist_ok=True)
    purge_report_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    # Transition job state to SOURCE_PURGED
    state_db = p_dir / "state.sqlite"
    if state_db.exists():
        store = JobStore(state_db)
        act = store.active_job("build")
        if act:
            store.transition(str(act["job_id"]), JobState.SOURCE_PURGED)
        store.close()

    return result
