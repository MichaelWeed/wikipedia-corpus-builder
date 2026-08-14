from typing import Literal

from pydantic import BaseModel, ConfigDict


class CategoryTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    traversed: int
    included: int
    excluded: int
    reviewed: int


class ReportSamples(BaseModel):
    model_config = ConfigDict(extra="forbid")

    included: list[str]
    borderline: list[str]


class BuildReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_fingerprint: str
    corpussieve_version: str
    domain_hash: str
    lock_hash: str
    model_info: str | None = None
    category_totals: CategoryTotals
    selected_articles: int
    counts_by_root: dict[str, int]
    counts_by_depth: dict[int, int]
    forced_counts: dict[str, int]
    warnings: list[str]
    samples: ReportSamples
    extraction_count: int
    normalization_errors: int
    output_bytes: int
    validation: Literal["PASSED", "FAILED", "NOT_RUN"]
    purge_eligible: bool
