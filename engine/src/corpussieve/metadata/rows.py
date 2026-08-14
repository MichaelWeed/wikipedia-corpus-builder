from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from corpussieve.contracts.enums import MemberType
from corpussieve.metadata.sqlparse import iter_insert_tuples
from corpussieve.metadata.titles import normalize_title


@dataclass(frozen=True)
class PageRow:
    page_id: int
    page_namespace: int
    page_title: str
    page_is_redirect: int


@dataclass(frozen=True)
class CategoryLinkRow:
    cl_from: int
    cl_to: str
    cl_type: MemberType


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


def iter_categorylinks_rows(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[CategoryLinkRow]:
    """Iterate over MediaWiki categorylinks.sql.gz rows."""
    for row in iter_insert_tuples(path, "categorylinks", chunk_size=chunk_size):
        if len(row) < 7:
            continue
        try:
            cl_from = int(row[0])
            raw_to = str(row[1])
            raw_type = str(row[6]).lower()

            if raw_type == "page":
                member_type = MemberType.PAGE
            elif raw_type == "subcat":
                member_type = MemberType.SUBCAT
            else:
                # Skip 'file' or unknown cl_type
                continue

            normalized_to = normalize_title(raw_to)
            yield CategoryLinkRow(
                cl_from=cl_from,
                cl_to=normalized_to,
                cl_type=member_type,
            )
        except (ValueError, TypeError):
            continue
