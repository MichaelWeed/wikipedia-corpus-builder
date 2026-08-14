from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from corpussieve.contracts.enums import AmbiguousBranchPolicy, SelectionMode


class DomainPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: SelectionMode = SelectionMode.BALANCED
    ambiguous_branch: AmbiguousBranchPolicy = AmbiguousBranchPolicy.REVIEW
    max_total_categories: int = 100_000
    max_total_articles: int = 2_000_000
    include_redirects: bool = False


class DomainRoot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    max_depth: int = 6


class DomainFacets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class DomainDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    name: str
    description: str
    language: str
    policy: DomainPolicy = Field(default_factory=DomainPolicy)
    facets: DomainFacets = Field(default_factory=DomainFacets)
    roots: list[DomainRoot] = Field(min_length=1)
    hard_exclude_pages: list[str] = Field(default_factory=list)
    forced_include_pages: list[str] = Field(default_factory=list)
    exclude_categories: list[str] = Field(default_factory=list)
