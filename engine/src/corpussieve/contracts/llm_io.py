from pydantic import BaseModel, ConfigDict, Field

from corpussieve.contracts.enums import BranchDecision


class FacetProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include: list[str]
    exclude: list[str]
    rationale: str


class BoundaryQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    options: list[str]
    recommended: str
    rationale: str


class BranchReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: BranchDecision
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    needs_human_review: bool
