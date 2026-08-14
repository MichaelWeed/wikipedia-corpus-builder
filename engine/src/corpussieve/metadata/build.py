import os
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from corpussieve import __version__
from corpussieve.contracts.enums import MemberType
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.events import ProgressEvent
from corpussieve.metadata.rows import (
    detect_categorylinks_schema,
    iter_categorylinks_rows,
    iter_linktarget_rows,
    iter_page_rows,
)

if TYPE_CHECKING:
    from corpussieve.sources.base import SourceAdapter

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def build_metadata_index(
    adapter: "SourceAdapter",
    db_path: Path,
    progress: Callable[[ProgressEvent], None] | None = None,
) -> None:
    """Build atomic SQLite metadata index database from source dump adapter.

    Reads page.sql.gz and categorylinks.sql.gz in batches of 5000 rows.
    Writes atomically to <db_path>.building and renames over target on success.
    """
    inspection = adapter.inspect()
    if not inspection.has_page_sql or not inspection.has_categorylinks_sql:
        raise CorpusSieveError(
            ErrorCode.SOURCE_COMPANION_MISSING,
            "Metadata index build requires page.sql.gz and categorylinks.sql.gz dumps.",
        )

    # Locate companion paths via adapter
    if not hasattr(adapter, "_locate_files"):
        raise CorpusSieveError(
            ErrorCode.SOURCE_UNSUPPORTED,
            "Source adapter does not support file inspection for metadata build.",
        )

    locate_fn: Callable[[], tuple[dict[str, Path], str, str, str]] = adapter._locate_files
    kind_to_path, _, _, _ = locate_fn()
    page_sql_path = kind_to_path["page.sql.gz"]
    cl_sql_path = kind_to_path["categorylinks.sql.gz"]

    _cl_columns, cl_is_current_schema = detect_categorylinks_schema(cl_sql_path)
    linktarget_path: Path | None = kind_to_path.get("linktarget.sql.gz")
    if cl_is_current_schema and linktarget_path is None:
        raise CorpusSieveError(
            ErrorCode.SOURCE_COMPANION_MISSING,
            "This dump's categorylinks.sql.gz uses the current MediaWiki schema "
            "(cl_target_id), which requires a companion linktarget.sql.gz to "
            "resolve category names. Download <proj>-<date>-linktarget.sql.gz "
            "alongside the other dump files.",
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    building_path = db_path.with_name(db_path.name + ".building")
    if building_path.exists():
        building_path.unlink()

    conn = sqlite3.connect(building_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")

        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)

        # 1. Insert pages table & track ns-14 category pages
        cat_page_id_to_name: dict[int, str] = {}
        cat_page_name_to_id: dict[str, int] = {}
        page_batch: list[tuple[int, int, str, int]] = []
        processed_pages = 0
        batch_size = 5000

        page_sql_query = (
            "INSERT INTO pages (page_id, page_namespace, title, is_redirect) VALUES (?, ?, ?, ?)"
        )

        for p_row in iter_page_rows(page_sql_path):
            page_batch.append(
                (
                    p_row.page_id,
                    p_row.page_namespace,
                    p_row.page_title,
                    p_row.page_is_redirect,
                )
            )
            if p_row.page_namespace == 14:
                cat_page_id_to_name[p_row.page_id] = p_row.page_title
                cat_page_name_to_id[p_row.page_title] = p_row.page_id

            if len(page_batch) >= batch_size:
                conn.executemany(page_sql_query, page_batch)
                conn.commit()
                processed_pages += len(page_batch)
                page_batch = []
                if progress:
                    progress(
                        ProgressEvent(
                            job_id="metadata",
                            stage="indexing_pages",
                            completed_units=processed_pages,
                            total_units=None,
                            message=f"Indexed {processed_pages} pages",
                        )
                    )

        if page_batch:
            conn.executemany(page_sql_query, page_batch)
            conn.commit()
            processed_pages += len(page_batch)

        # 2. If categorylinks uses the current schema (cl_target_id), first build
        #    an lt_id -> category-title map from linktarget.sql.gz, restricted to
        #    namespace 14 (Category). Scoped to category count, not link count —
        #    same order of magnitude as the existing cat_page_id_to_name map above.
        linktarget_id_to_title: dict[int, str] = {}
        if linktarget_path is not None:
            for processed_lt, lt_row in enumerate(iter_linktarget_rows(linktarget_path), start=1):
                if lt_row.lt_namespace == 14:
                    linktarget_id_to_title[lt_row.lt_id] = lt_row.lt_title
                if progress and processed_lt % batch_size == 0:
                    progress(
                        ProgressEvent(
                            job_id="metadata",
                            stage="indexing_linktarget",
                            completed_units=processed_lt,
                            total_units=None,
                            message=f"Indexed {processed_lt} link targets",
                        )
                    )

        # 3. Insert category_membership & category_edges
        membership_batch: list[tuple[str, int, str]] = []
        edges_batch: list[tuple[str, str]] = []
        all_categories: set[str] = set(cat_page_name_to_id.keys())

        mem_sql_query = (
            "INSERT OR IGNORE INTO category_membership (category, page_id, member_type) "
            "VALUES (?, ?, ?)"
        )
        edge_sql_query = (
            "INSERT OR IGNORE INTO category_edges (parent_category, child_category) VALUES (?, ?)"
        )

        processed_cl = 0
        resolved_cl = 0
        unresolved_target_ids = 0
        for processed_cl, cl_row in enumerate(iter_categorylinks_rows(cl_sql_path), start=1):
            resolved_to: str | None
            if cl_row.cl_to is not None:
                resolved_to = cl_row.cl_to
            elif cl_row.cl_target_id is not None:
                resolved_to = linktarget_id_to_title.get(cl_row.cl_target_id)
            else:
                resolved_to = None

            if resolved_to is None:
                unresolved_target_ids += 1
                continue
            cl_to = resolved_to

            resolved_cl += 1
            all_categories.add(cl_to)

            if cl_row.cl_type == MemberType.PAGE:
                membership_batch.append((cl_to, cl_row.cl_from, "page"))
            elif cl_row.cl_type == MemberType.SUBCAT:
                child_cat_name = cat_page_id_to_name.get(cl_row.cl_from)
                if child_cat_name:
                    all_categories.add(child_cat_name)
                    edges_batch.append((cl_to, child_cat_name))

            if len(membership_batch) >= batch_size:
                conn.executemany(mem_sql_query, membership_batch)
                membership_batch = []

            if len(edges_batch) >= batch_size:
                conn.executemany(edge_sql_query, edges_batch)
                edges_batch = []

            if processed_cl % batch_size == 0:
                conn.commit()
                if progress:
                    progress(
                        ProgressEvent(
                            job_id="metadata",
                            stage="indexing_categorylinks",
                            completed_units=processed_cl,
                            total_units=None,
                            message=f"Indexed {processed_cl} category links",
                        )
                    )

        if membership_batch:
            conn.executemany(mem_sql_query, membership_batch)
        if edges_batch:
            conn.executemany(edge_sql_query, edges_batch)
        conn.commit()

        # Fail loudly rather than silently producing an empty category graph:
        # a non-trivial categorylinks file that resolves nothing indicates a
        # schema mismatch (e.g. missing/stale linktarget data), not "no categories".
        if processed_cl >= 1000 and resolved_cl == 0:
            raise CorpusSieveError(
                ErrorCode.METADATA_PARSE_FAILED,
                f"Parsed {processed_cl} categorylinks rows but resolved 0 category "
                f"names ({unresolved_target_ids} unresolved cl_target_id lookups). "
                "This usually means linktarget.sql.gz is missing, stale, or from a "
                "different dump date than categorylinks.sql.gz.",
            )

        # 3. Populate categories table
        cat_batch: list[tuple[str, int | None]] = [
            (cat_name, cat_page_name_to_id.get(cat_name)) for cat_name in all_categories
        ]
        for i in range(0, len(cat_batch), batch_size):
            conn.executemany(
                "INSERT OR IGNORE INTO categories (category, page_id) VALUES (?, ?)",
                cat_batch[i : i + batch_size],
            )
        conn.commit()

        # 4. Write meta table
        built_at = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        meta_rows = [
            ("schema_version", "1"),
            ("source_fingerprint", inspection.fingerprint.fingerprint),
            ("built_at", built_at),
            ("corpussieve_version", __version__),
        ]
        conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", meta_rows)
        conn.commit()

    except Exception as e:
        conn.close()
        if building_path.exists():
            building_path.unlink()
        if isinstance(e, CorpusSieveError):
            raise
        raise CorpusSieveError(
            ErrorCode.METADATA_PARSE_FAILED,
            f"Failed to build metadata index: {e}",
        ) from e
    else:
        conn.close()
        # Atomic rename
        if db_path.exists():
            db_path.unlink()
        building_path.replace(db_path)
        os.sync() if hasattr(os, "sync") else None
