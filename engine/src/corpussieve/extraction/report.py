import json
from pathlib import Path

from corpussieve import __version__
from corpussieve.contracts.lock import DomainLock
from corpussieve.contracts.report import BuildReport, CategoryTotals, ReportSamples
from corpussieve.validation.validate import ValidationResult


def assemble_build_report(
    lock: DomainLock,
    validation_res: ValidationResult,
    extraction_count: int,
    output_bytes: int,
    warnings: list[str],
) -> BuildReport:
    """Assemble BuildReport metadata document from extraction and validation results."""
    # Count decisions
    traversed = len(lock.category_decisions)
    included = sum(1 for d in lock.category_decisions if str(d.decision) == "include")
    excluded = sum(1 for d in lock.category_decisions if str(d.decision) == "exclude")
    reviewed = sum(1 for d in lock.category_decisions if str(d.decision) == "review")

    cat_totals = CategoryTotals(
        traversed=traversed,
        included=included,
        excluded=excluded,
        reviewed=reviewed,
    )

    sample_inc = [d.category for d in lock.category_decisions if str(d.decision) == "include"][:10]
    samples = ReportSamples(included=sample_inc, borderline=[])

    model_info_str = None
    if lock.llm:
        model_info_str = f"{lock.llm.provider}/{lock.llm.model_id}"

    purge_eligible = validation_res.status == "PASSED" and len(validation_res.errors) == 0

    return BuildReport(
        source_fingerprint=lock.source_fingerprint,
        corpussieve_version=__version__,
        domain_hash=lock.domain_hash,
        lock_hash=lock.lock_hash,
        model_info=model_info_str,
        category_totals=cat_totals,
        selected_articles=extraction_count,
        counts_by_root={},
        counts_by_depth={},
        forced_counts={},
        warnings=warnings,
        samples=samples,
        extraction_count=extraction_count,
        normalization_errors=0,
        output_bytes=output_bytes,
        validation="PASSED" if validation_res.status == "PASSED" else "FAILED",
        purge_eligible=purge_eligible,
    )


def write_build_report(
    report: BuildReport, corpus_dir: Path | str, project_dir: Path | str | None = None
) -> None:
    """Write build-report.json to corpus directory and append summary to project reports/."""
    c_dir = Path(corpus_dir).resolve()
    c_dir.mkdir(parents=True, exist_ok=True)
    r_file = c_dir / "build-report.json"

    data = report.model_dump(mode="json")
    json_str = json.dumps(data, indent=2, sort_keys=True) + "\n"
    r_file.write_text(json_str, encoding="utf-8")

    if project_dir:
        p_dir = Path(project_dir).resolve()
        reports_dir = p_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        summary_file = reports_dir / f"report-{report.lock_hash[:8]}.json"
        summary_file.write_text(json_str, encoding="utf-8")
