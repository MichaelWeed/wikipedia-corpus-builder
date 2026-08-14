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
from corpussieve.metadata.rows import iter_categorylinks_rows, iter_page_rows

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

    locate_fn = getattr(adapter, "_locate_files")
    kind_to_path, _, _, _ = locate_fn()
    page_sql_path = kind_to_path["page.sql.gz"]
    cl_sql_path = kind_to_path["categorylinks.sql.gz"]

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

        # 2. Insert category_membership & category_edges
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

        for processed_cl, cl_row in enumerate(iter_categorylinks_rows(cl_sql_path), start=1):
            all_categories.add(cl_row.cl_to)

            if cl_row.cl_type == MemberType.PAGE:
                membership_batch.append((cl_row.cl_to, cl_row.cl_from, "page"))
            elif cl_row.cl_type == MemberType.SUBCAT:
                child_cat_name = cat_page_id_to_name.get(cl_row.cl_from)
                if child_cat_name:
                    all_categories.add(child_cat_name)
                    edges_batch.append((cl_row.cl_to, child_cat_name))

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
