from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from corpussieve.contracts.events import ProgressEvent
from corpussieve.contracts.source import SourceFingerprint, SourceInspection


@dataclass
class RawPage:
    page_id: int
    namespace: int
    title: str
    revision_id: int
    redirect_target: str | None
    wikitext: str


class SourceAdapter(ABC):
    """Abstract base class for all CorpusSieve source adapters."""

    @abstractmethod
    def inspect(self) -> SourceInspection:
        """Inspect source files and locate companion dumps."""

    @abstractmethod
    def fingerprint(self) -> SourceFingerprint:
        """Compute quick fingerprint digest of source files."""

    @abstractmethod
    def build_metadata_index(
        self,
        db_path: Path,
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        """Build SQLite metadata index from categorylinks and page SQL dumps."""

    @abstractmethod
    def enumerate_pages(self) -> Iterator[RawPage]:
        """Stream all raw pages from source dumps."""

    @abstractmethod
    def extract_selected_pages(
        self,
        page_ids: set[int],
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> Iterator[RawPage]:
        """Extract selected page IDs from source dumps."""

    @abstractmethod
    def source_metadata(self) -> dict[str, Any]:
        """Return dict of source-level metadata."""
