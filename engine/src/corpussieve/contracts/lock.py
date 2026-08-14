from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from corpussieve.contracts.enums import BranchDecision
from corpussieve.contracts.hashing import canonical_json_hash


class ResolvedRoot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    resolved_category: str
    max_depth: int


class CategoryDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    decision: BranchDecision
    source: Literal["traversal", "facet_exclude", "llm", "human"]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str
    root: str | None = None
    depth: int | None = None


class LlmProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    prompt_version: str
    schema_version: str


class DomainLock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    domain_id: str
    domain_hash: str
    source_fingerprint: str
    resolved_roots: list[ResolvedRoot]
    category_decisions: list[CategoryDecision]
    hard_exclude_pages: list[str] = Field(default_factory=list)
    forced_include_pages: list[str] = Field(default_factory=list)
    llm: LlmProvenance | None = None
    compiler_version: str
    compiled_at: str
    warnings_acknowledged: list[str] = Field(default_factory=list)
    lock_hash: str

    @classmethod
    def compute_hash(cls, data: dict[str, Any]) -> str:
        """Compute lock_hash over canonical JSON excluding lock_hash itself."""
        clean = {k: v for k, v in data.items() if k != "lock_hash"}
        return canonical_json_hash(clean)
