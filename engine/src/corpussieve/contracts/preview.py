from typing import Literal

from pydantic import BaseModel, ConfigDict


class DomainPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    article_count: int
    estimated_output_bytes: int
    counts_by_root: dict[str, int]
    counts_by_depth: dict[int, int]
    sample_included: list[str]
    sample_borderline: list[str]
    contamination_groups: dict[str, list[str]]
    warnings: list[str]


class ExplainResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    status: Literal["included", "excluded", "absent"]
    provenance_chain: list[str]
    reason: str
