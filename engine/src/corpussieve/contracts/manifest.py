from typing import Literal

from pydantic import BaseModel, ConfigDict


class SelectionReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str
    depth: int
    via_category: str
    reason_type: Literal["category_path", "forced_include"]


class ManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    project: str
    language: str
    page_id: int
    title: str
    namespace: int
    selected: bool
    selection: SelectionReason
    revision_id: int | None = None
    content_hash: str | None = None
    document_id: str | None = None
