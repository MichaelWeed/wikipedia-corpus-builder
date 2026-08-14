from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from corpussieve.contracts.enums import MemberType
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.metadata.sqlparse import iter_insert_tuples, parse_create_table_columns
from corpussieve.metadata.titles import normalize_title


@dataclass(frozen=True)
class PageRow:
    page_id: int
    page_namespace: int
    page_title: str
    page_is_redirect: int


@dataclass(frozen=True)
class LinkTargetRow:
    lt_id: int
    lt_namespace: int
    lt_title: str


@dataclass(frozen=True)
class CategoryLinkRow:
    """A row from categorylinks, normalized across MediaWiki schema versions.

    Legacy schema (has a `cl_to` column): the category title is inline;
    `cl_to` is set and `cl_target_id` is None.

    Current schema (MediaWiki 1.39+, has `cl_target_id` instead of `cl_to`):
    the category title lives in a separate `linktarget` table; `cl_target_id`
    is set and `cl_to` is None until resolved via a linktarget join.
    """

    cl_from: int
    cl_type: MemberType
    cl_to: str | None = None
    cl_target_id: int | None = None


def iter_page_rows(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[PageRow]:
    """Iterate over MediaWiki page.sql.gz rows.

    Column layout: (page_id, page_namespace, page_title, page_restrictions, page_is_redirect, ...)
    """
    for row in iter_insert_tuples(path, "page", chunk_size=chunk_size):
        if len(row) < 5:
            continue
        try:
            page_id = int(row[0])
            namespace = int(row[1])
            raw_title = str(row[2])
            is_redirect = int(row[4])
            normalized_title = normalize_title(raw_title)
            yield PageRow(
                page_id=page_id,
                page_namespace=namespace,
                page_title=normalized_title,
                page_is_redirect=is_redirect,
            )
        except (ValueError, TypeError):
            continue


def detect_categorylinks_schema(path: Path) -> tuple[list[str], bool]:
    """Return (column_names, is_current_schema) for a categorylinks.sql.gz dump.

    `is_current_schema` is True when the dump uses `cl_target_id` (MediaWiki
    1.39+, resolved via a separate linktarget table) rather than the legacy
    inline `cl_to` column. Raises METADATA_PARSE_FAILED if neither column is
    present, since row parsing cannot proceed without knowing which it is.
    """
    columns = parse_create_table_columns(path, "categorylinks")
    if not columns:
        raise CorpusSieveError(
            ErrorCode.METADATA_PARSE_FAILED,
            f"Could not locate CREATE TABLE `categorylinks` in '{path}'.",
        )
    if "cl_to" in columns:
        return columns, False
    if "cl_target_id" in columns:
        return columns, True
    raise CorpusSieveError(
        ErrorCode.METADATA_PARSE_FAILED,
        f"categorylinks schema in '{path}' has neither `cl_to` nor "
        f"`cl_target_id` (columns: {columns}). Unrecognized schema version.",
    )


def iter_categorylinks_rows(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[CategoryLinkRow]:
    """Iterate over MediaWiki categorylinks.sql.gz rows.

    Column order is read from the dump's own CREATE TABLE statement, so this
    works across the schema migration that replaced `cl_to` (category title
    inline) with `cl_target_id` (a foreign key into a separate `linktarget`
    table, MediaWiki 1.39+). Current-schema rows carry `cl_target_id` unresolved;
    callers must join against `iter_linktarget_rows` to recover category titles.
    """
    columns, is_current = detect_categorylinks_schema(path)
    idx_from = columns.index("cl_from")
    idx_type = columns.index("cl_type")
    idx_to = columns.index("cl_to") if not is_current else None
    idx_target = columns.index("cl_target_id") if is_current else None
    min_len = max(idx_from, idx_type, idx_to or 0, idx_target or 0) + 1

    for row in iter_insert_tuples(path, "categorylinks", chunk_size=chunk_size):
        if len(row) < min_len:
            continue
        try:
            cl_from = int(row[idx_from])
            raw_type = str(row[idx_type]).lower()

            if raw_type == "page":
                member_type = MemberType.PAGE
            elif raw_type == "subcat":
                member_type = MemberType.SUBCAT
            else:
                # Skip 'file' or unknown cl_type
                continue

            if is_current:
                assert idx_target is not None
                yield CategoryLinkRow(
                    cl_from=cl_from,
                    cl_type=member_type,
                    cl_target_id=int(row[idx_target]),
                )
            else:
                assert idx_to is not None
                normalized_to = normalize_title(str(row[idx_to]))
                yield CategoryLinkRow(
                    cl_from=cl_from,
                    cl_type=member_type,
                    cl_to=normalized_to,
                )
        except (ValueError, TypeError):
            continue


def iter_linktarget_rows(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[LinkTargetRow]:
    """Iterate over MediaWiki linktarget.sql.gz rows (lt_id, lt_namespace, lt_title)."""
    columns = parse_create_table_columns(path, "linktarget")
    if not columns:
        raise CorpusSieveError(
            ErrorCode.METADATA_PARSE_FAILED,
            f"Could not locate CREATE TABLE `linktarget` in '{path}'.",
        )
    idx_id = columns.index("lt_id")
    idx_ns = columns.index("lt_namespace")
    idx_title = columns.index("lt_title")
    min_len = max(idx_id, idx_ns, idx_title) + 1

    for row in iter_insert_tuples(path, "linktarget", chunk_size=chunk_size):
        if len(row) < min_len:
            continue
        try:
            yield LinkTargetRow(
                lt_id=int(row[idx_id]),
                lt_namespace=int(row[idx_ns]),
                lt_title=normalize_title(str(row[idx_title])),
            )
        except (ValueError, TypeError):
            continue
