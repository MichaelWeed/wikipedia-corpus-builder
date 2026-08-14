from typing import Literal

from pydantic import BaseModel, ConfigDict


class FacetProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_facets: list[str]
    exclude_facets: list[str]
    rationale: str


class BoundaryQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    recommended: Literal["include", "exclude"]
    facet_target: str


class BoundaryQuestionsList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[BoundaryQuestion]
