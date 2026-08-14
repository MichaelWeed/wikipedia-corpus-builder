import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from corpussieve.contracts.enums import JobState
from corpussieve.domain.lock_build import read_lock
from corpussieve.jobs.state import JobStore
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter
from corpussieve.validation.validate import validate_corpus

logger = logging.getLogger(__name__)


class PurgeBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    detail: dict[str, Any] = {}


class PurgePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_dir: str
    project_name: str
    files_to_delete: list[str]
    total_bytes: int
    reversible: bool
    corpus_path: str
    report_summary: dict[str, Any]


def check_purge_preconditions(
    project_dir: Path | str,
    output_dir: Path | str | None = None,
) -> tuple[PurgePlan | None, list[PurgeBlocker]]:
    """Check all 7 purge preconditions from design §16.2."""
    p_dir = Path(project_dir).resolve()
    blockers: list[PurgeBlocker] = []

    # 1. State DB & job state == VALIDATED or EXPORTED
    state_db = p_dir / "state.sqlite"
    if not state_db.exists():
        blockers.append(
            PurgeBlocker(
                code="PURGE_OUTPUT_UNVERIFIED",
                message="Project state database does not exist.",
            )
        )
        return None, blockers

    store = JobStore(state_db)
    cursor = store._conn.execute(
        "SELECT state FROM jobs WHERE kind = 'build' ORDER BY updated_at DESC LIMIT 1"
    )
    row = cursor.fetchone()
    store.close()

    valid_states = {
        JobState.VALIDATED.value,
        JobState.EXPORTED.value,
        "VALIDATED",
        "EXPORTED",
    }
    if not row or row["state"] not in valid_states:
        blockers.append(
            PurgeBlocker(
                code="PURGE_OUTPUT_UNVERIFIED",
                message="Build job state is not VALIDATED or EXPORTED.",
            )
        )
        return None, blockers

    # 2. Build report validation status == PASSED
    target_corpus = Path(output_dir).resolve() if output_dir else p_dir / "output" / "corpus"
    if not target_corpus.exists() and (p_dir / "corpus").exists():
        target_corpus = p_dir / "corpus"

    report_file = target_corpus / "build-report.json"
    if not report_file.exists():
        report_file = p_dir / "reports" / "build-report.json"
    if not report_file.exists() and (p_dir / "reports").exists():
        rep_list = list((p_dir / "reports").glob("report-*.json"))
        if rep_list:
            report_file = rep_list[0]

    if not report_file.exists():
        blockers.append(
            PurgeBlocker(
                code="PURGE_OUTPUT_UNVERIFIED",
                message="Build report does not exist.",
            )
        )
        return None, blockers

    report_data = json.loads(report_file.read_text(encoding="utf-8"))
    if report_data.get("validation") != "PASSED":
        blockers.append(
            PurgeBlocker(
                code="PURGE_OUTPUT_UNVERIFIED",
                message="Validation status in build report is not PASSED.",
            )
        )

    # 3. Source re-fingerprint match check
    source_dir = p_dir / "source"
    proj_file = p_dir / "project.yaml"
    if proj_file.exists():
        try:
            import yaml  # type: ignore[import-untyped]

            data = yaml.safe_load(proj_file.read_text(encoding="utf-8"))
            if data and isinstance(data, dict) and data.get("source_paths"):
                sp = data["source_paths"]
                if isinstance(sp, list) and sp:
                    raw_sp = Path(sp[0])
                    source_dir = raw_sp if raw_sp.is_absolute() else (p_dir / raw_sp).resolve()
        except Exception as exc:
            logger.warning("Failed to read project.yaml source_paths: %s", exc)

    if not source_dir.exists():
        blockers.append(
            PurgeBlocker(
                code="PURGE_SOURCE_CHANGED",
                message="Source directory does not exist.",
            )
        )
        return None, blockers

    adapter = WikimediaXmlDumpAdapter(source_dir)
    curr_fp = adapter.fingerprint().fingerprint
    exp_fp = report_data.get("source_fingerprint", "")
    if curr_fp != exp_fp:
        msg = f"Source fingerprint changed (expected {exp_fp[:8]}, current {curr_fp[:8]})."
        blockers.append(
            PurgeBlocker(
                code="PURGE_SOURCE_CHANGED",
                message=msg,
            )
        )

    # 4. Canonical corpus validation
    target_corpus = Path(output_dir).resolve() if output_dir else p_dir / "output" / "corpus"
    if not target_corpus.exists() and (p_dir / "corpus").exists():
        target_corpus = p_dir / "corpus"

    lock_file = target_corpus / "domain.lock.json"
    if not lock_file.exists() and (p_dir / "domains").exists():
        locks = list((p_dir / "domains").glob("*.lock.json"))
        if locks:
            lock_file = locks[0]

    if not lock_file.exists():
        blockers.append(
            PurgeBlocker(
                code="PURGE_OUTPUT_UNVERIFIED",
                message="Domain lockfile does not exist for canonical corpus validation.",
            )
        )
    else:
        lock = read_lock(lock_file)
        val_res = validate_corpus(target_corpus, lock)
        if val_res.status != "PASSED":
            blockers.append(
                PurgeBlocker(
                    code="PURGE_OUTPUT_UNVERIFIED",
                    message="Canonical corpus re-validation failed.",
                )
            )

    # 5. Path safety checks
    resolved_source_dir = source_dir.resolve()
    if (
        target_corpus == resolved_source_dir
        or target_corpus in resolved_source_dir.parents
        or resolved_source_dir in target_corpus.parents
    ):
        blockers.append(
            PurgeBlocker(
                code="output_inside_target",
                message="Output directory overlaps with source delete targets.",
            )
        )

    delete_files: list[Path] = []
    total_bytes = 0
    items_to_check = list(source_dir.rglob("*")) if source_dir.is_dir() else [source_dir]
    for item in items_to_check:
        if item.is_file() or item.is_symlink():
            resolved_item = item.resolve()

            # Symlink escape check
            msg = f"Symlink '{item}' resolves outside source scope ({resolved_item})."
            try:
                if not resolved_item.is_relative_to(resolved_source_dir):
                    blockers.append(
                        PurgeBlocker(
                            code="symlink_escape_scope",
                            message=msg,
                        )
                    )
                    break
            except ValueError:
                blockers.append(
                    PurgeBlocker(
                        code="symlink_escape_scope",
                        message=msg,
                    )
                )
                break

            # Canonical check: output dir must not be inside target and target not inside output
            if target_corpus in resolved_item.parents or resolved_item in target_corpus.parents:
                blockers.append(
                    PurgeBlocker(
                        code="output_inside_target",
                        message="Output directory overlaps with source delete targets.",
                    )
                )
                break

            delete_files.append(resolved_item)
            if resolved_item.exists():
                total_bytes += resolved_item.stat().st_size

    if blockers:
        return None, blockers

    proj_name = p_dir.name
    plan = PurgePlan(
        project_dir=str(p_dir),
        project_name=proj_name,
        files_to_delete=[str(f) for f in delete_files],
        total_bytes=total_bytes,
        reversible=True,
        corpus_path=str(target_corpus),
        report_summary={
            "selected_articles": report_data.get("selected_articles", 0),
            "extraction_count": report_data.get("extraction_count", 0),
        },
    )
    return plan, []
