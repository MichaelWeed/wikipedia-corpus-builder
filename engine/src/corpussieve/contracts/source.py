from typing import Literal

from pydantic import BaseModel, ConfigDict


class SourceFileInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    size_bytes: int
    mtime_iso: str
    quick_hash: str


class SourceFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str
    language: str
    dump_date: str | None = None
    files: list[SourceFileInfo]
    fingerprint: str
    official_checksum_verified: bool = False
    full_hash: str | None = None


class SourceInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: Literal["wikimedia_xml_dump"] = "wikimedia_xml_dump"
    dump_kind: Literal["multistream", "sequential"]
    has_multistream_index: bool
    has_page_sql: bool
    has_categorylinks_sql: bool
    has_linktarget: bool = False
    warnings: list[str]
    fingerprint: SourceFingerprint
