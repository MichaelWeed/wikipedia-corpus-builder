from typing import Literal

from pydantic import BaseModel, ConfigDict

from corpussieve.contracts.manifest import SelectionReason


class CorpusSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str
    language: str
    page_id: int
    revision_id: int
    title: str
    source_url: str
    dump_date: str | None = None


class CorpusContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["wikitext", "markdown"] = "wikitext"
    raw: str


class CorpusRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    source: CorpusSource
    categories: list[str]
    selection: SelectionReason
    content: CorpusContent
