from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from corpussieve.contracts.events import ProgressEvent
from corpussieve.contracts.source import SourceFingerprint, SourceInspection
from corpussieve.sources.base import RawPage, SourceAdapter


class MediaWikiContentExportAdapter(SourceAdapter):
    """Post-MVP stub for MediaWiki Content Export XML API dumps."""

    def inspect(self) -> SourceInspection:
        raise NotImplementedError("MediaWikiContentExportAdapter is a post-MVP adapter stub.")

    def fingerprint(self) -> SourceFingerprint:
        raise NotImplementedError("MediaWikiContentExportAdapter is a post-MVP adapter stub.")

    def build_metadata_index(
        self,
        db_path: Path,
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        raise NotImplementedError("MediaWikiContentExportAdapter is a post-MVP adapter stub.")

    def enumerate_pages(self) -> Iterator[RawPage]:
        raise NotImplementedError("MediaWikiContentExportAdapter is a post-MVP adapter stub.")

    def extract_selected_pages(
        self,
        page_ids: set[int],
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> Iterator[RawPage]:
        raise NotImplementedError("MediaWikiContentExportAdapter is a post-MVP adapter stub.")

    def source_metadata(self) -> dict[str, Any]:
        raise NotImplementedError("MediaWikiContentExportAdapter is a post-MVP adapter stub.")


class WikimediaEnterpriseSnapshotAdapter(SourceAdapter):
    """Post-MVP stub for Wikimedia Enterprise JSON snapshots."""

    def inspect(self) -> SourceInspection:
        raise NotImplementedError("WikimediaEnterpriseSnapshotAdapter is a post-MVP adapter stub.")

    def fingerprint(self) -> SourceFingerprint:
        raise NotImplementedError("WikimediaEnterpriseSnapshotAdapter is a post-MVP adapter stub.")

    def build_metadata_index(
        self,
        db_path: Path,
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        raise NotImplementedError("WikimediaEnterpriseSnapshotAdapter is a post-MVP adapter stub.")

    def enumerate_pages(self) -> Iterator[RawPage]:
        raise NotImplementedError("WikimediaEnterpriseSnapshotAdapter is a post-MVP adapter stub.")

    def extract_selected_pages(
        self,
        page_ids: set[int],
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> Iterator[RawPage]:
        raise NotImplementedError("WikimediaEnterpriseSnapshotAdapter is a post-MVP adapter stub.")

    def source_metadata(self) -> dict[str, Any]:
        raise NotImplementedError("WikimediaEnterpriseSnapshotAdapter is a post-MVP adapter stub.")


class WikimediaStructuredContentsAdapter(SourceAdapter):
    """Post-MVP stub for Wikimedia Structured Data / Abstract dumps."""

    def inspect(self) -> SourceInspection:
        raise NotImplementedError("WikimediaStructuredContentsAdapter is a post-MVP adapter stub.")

    def fingerprint(self) -> SourceFingerprint:
        raise NotImplementedError("WikimediaStructuredContentsAdapter is a post-MVP adapter stub.")

    def build_metadata_index(
        self,
        db_path: Path,
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        raise NotImplementedError("WikimediaStructuredContentsAdapter is a post-MVP adapter stub.")

    def enumerate_pages(self) -> Iterator[RawPage]:
        raise NotImplementedError("WikimediaStructuredContentsAdapter is a post-MVP adapter stub.")

    def extract_selected_pages(
        self,
        page_ids: set[int],
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> Iterator[RawPage]:
        raise NotImplementedError("WikimediaStructuredContentsAdapter is a post-MVP adapter stub.")

    def source_metadata(self) -> dict[str, Any]:
        raise NotImplementedError("WikimediaStructuredContentsAdapter is a post-MVP adapter stub.")
