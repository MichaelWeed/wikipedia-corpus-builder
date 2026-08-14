from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BranchReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    decision: Literal["include", "exclude", "review"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    needs_human_review: bool = False
