from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.events import ProgressEvent
from corpussieve.contracts.source import SourceFingerprint, SourceInspection
from corpussieve.extraction.multistream import extract_multistream
from corpussieve.extraction.sequential import extract_sequential
from corpussieve.sources.base import RawPage, SourceAdapter
from corpussieve.sources.fingerprint import fingerprint_files
from corpussieve.sources.wikimedia.naming import parse_dump_filename


class WikimediaXmlDumpAdapter(SourceAdapter):
    """Adapter for MediaWiki XML export and SQL category/page dumps."""

    def __init__(self, source: Path | str) -> None:
        self.source_path = Path(source).resolve()

    def _locate_files(self) -> tuple[dict[str, Path], str, str, str]:
        """Locate recognizable dump files in source directory or file."""
        if not self.source_path.exists():
            raise CorpusSieveError(
                ErrorCode.SOURCE_UNSUPPORTED,
                f"Source path '{self.source_path}' does not exist.",
            )

        search_dir = self.source_path if self.source_path.is_dir() else self.source_path.parent

        candidates: list[tuple[Path, str, str, str, str]] = []
        for file in search_dir.iterdir():
            if not file.is_file():
                continue
            parts = parse_dump_filename(file.name)
            if parts:
                candidates.append((file, parts.project, parts.language, parts.date, parts.kind))

        if not candidates:
            raise CorpusSieveError(
                ErrorCode.SOURCE_UNSUPPORTED,
                f"No recognized Wikimedia dump files found in '{search_dir}'.",
            )

        if self.source_path.is_file():
            target_parts = parse_dump_filename(self.source_path.name)
            if target_parts:
                candidates = [
                    c
                    for c in candidates
                    if c[1] == target_parts.project and c[3] == target_parts.date
                ]

        if not candidates:
            raise CorpusSieveError(
                ErrorCode.SOURCE_UNSUPPORTED,
                f"Source file '{self.source_path}' is not a recognized dump file.",
            )

        primary_proj = candidates[0][1]
        primary_date = candidates[0][3]
        primary_lang = candidates[0][2]

        kind_to_path: dict[str, Path] = {}
        for file, proj, _lang, date, kind in candidates:
            if proj == primary_proj and date == primary_date:
                kind_to_path[kind] = file

        if (
            "pages-articles-multistream.xml.bz2" not in kind_to_path
            and "pages-articles.xml.bz2" not in kind_to_path
        ):
            raise CorpusSieveError(
                ErrorCode.SOURCE_UNSUPPORTED,
                f"No XML article dump found for project '{primary_proj}' date '{primary_date}'.",
            )

        return kind_to_path, primary_proj, primary_lang, primary_date

    def inspect(self) -> SourceInspection:
        kind_to_path, _project, _lang, _dump_date = self._locate_files()
        warnings: list[str] = []

        has_index = "pages-articles-multistream-index.txt.bz2" in kind_to_path
        has_page_sql = "page.sql.gz" in kind_to_path
        has_categorylinks_sql = "categorylinks.sql.gz" in kind_to_path
        has_linktarget = "linktarget.sql.gz" in kind_to_path

        if "pages-articles-multistream.xml.bz2" in kind_to_path:
            if has_index:
                dump_kind = "multistream"
            else:
                dump_kind = "sequential"
                warnings.append(
                    "Multistream XML found without companion index; falling back to sequential."
                )
        else:
            dump_kind = "sequential"

        if not has_page_sql:
            warnings.append("Companion page.sql.gz dump is missing.")

        if not has_categorylinks_sql:
            warnings.append("Companion categorylinks.sql.gz dump is missing.")
        elif not has_linktarget:
            from corpussieve.metadata.rows import detect_categorylinks_schema

            _cols, cl_is_current = detect_categorylinks_schema(kind_to_path["categorylinks.sql.gz"])
            if cl_is_current:
                warnings.append(
                    "This dump's categorylinks.sql.gz uses the current MediaWiki "
                    "schema (cl_target_id) and requires a companion "
                    "linktarget.sql.gz to resolve category names, which is missing. "
                    "Category traversal will not work without it."
                )

        fingerprint = self.fingerprint()

        return SourceInspection(
            adapter="wikimedia_xml_dump",
            dump_kind=dump_kind,  # type: ignore[arg-type]
            has_multistream_index=has_index,
            has_page_sql=has_page_sql,
            has_categorylinks_sql=has_categorylinks_sql,
            has_linktarget=has_linktarget,
            warnings=warnings,
            fingerprint=fingerprint,
        )

    def fingerprint(self) -> SourceFingerprint:
        kind_to_path, _project, _lang, _dump_date = self._locate_files()
        return fingerprint_files(list(kind_to_path.values()))

    def build_metadata_index(
        self,
        db_path: Path,
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        from corpussieve.metadata.build import build_metadata_index as do_build

        do_build(self, db_path, progress)

    def enumerate_pages(self) -> Iterator[RawPage]:
        kind_to_path, _project, _lang, _dump_date = self._locate_files()
        dump_file = (
            kind_to_path.get("pages-articles-multistream.xml.bz2")
            or kind_to_path["pages-articles.xml.bz2"]
        )
        yield from extract_sequential(dump_file, selected_ids=set(range(1, 10**9)))

    def extract_selected_pages(
        self,
        page_ids: set[int],
        _progress: Callable[[ProgressEvent], None] | None = None,
        job_store: Any = None,
        job_id: str | None = None,
    ) -> Iterator[RawPage]:
        kind_to_path, _project, _lang, _dump_date = self._locate_files()
        ms_xml = kind_to_path.get("pages-articles-multistream.xml.bz2")
        ms_idx = kind_to_path.get("pages-articles-multistream-index.txt.bz2")

        if ms_xml and ms_idx:
            yield from extract_multistream(
                ms_xml, ms_idx, page_ids, job_store=job_store, job_id=job_id
            )
        else:
            dump_file = ms_xml or kind_to_path["pages-articles.xml.bz2"]
            yield from extract_sequential(dump_file, page_ids, job_store=job_store, job_id=job_id)

    def source_metadata(self) -> dict[str, Any]:
        kind_to_path, project, lang, dump_date = self._locate_files()
        return {
            "project": project,
            "language": lang,
            "dump_date": dump_date,
            "files": list(kind_to_path.keys()),
        }
