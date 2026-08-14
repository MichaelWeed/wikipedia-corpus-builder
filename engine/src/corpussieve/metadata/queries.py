import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from corpussieve.contracts.enums import BranchDecision
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.metadata.rows import PageRow
from corpussieve.metadata.titles import normalize_title


@dataclass(frozen=True)
class CategoryHit:
    category: str
    direct_page_count: int
    subcat_count: int


@dataclass(frozen=True)
class MetadataStats:
    page_count: int
    category_count: int
    edge_count: int
    source_fingerprint: str
    built_at: str


class MetadataIndex:
    """Read-only query API for CorpusSieve SQLite metadata index."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).resolve()
        if not self.db_path.exists():
            raise CorpusSieveError(
                ErrorCode.METADATA_PARSE_FAILED,
                f"Metadata database file '{self.db_path}' does not exist.",
            )
        # Open in URI read-only mode by default
        uri = f"file:{self.db_path}?mode=ro"
        try:
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            raise CorpusSieveError(
                ErrorCode.METADATA_PARSE_FAILED,
                f"Failed to open metadata index '{self.db_path}': {e}",
            ) from e

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if hasattr(self, "_conn") and self._conn:
            self._conn.close()

    def child_categories(self, category: str) -> list[str]:
        """Return list of direct subcategories for parent category."""
        norm_cat = normalize_title(category)
        cursor = self._conn.execute(
            "SELECT child_category FROM category_edges WHERE parent_category = ?",
            (norm_cat,),
        )
        return [row["child_category"] for row in cursor.fetchall()]

    def member_page_ids(self, category: str, namespaces: tuple[int, ...] = (0,)) -> list[int]:
        """Return list of page IDs directly in category matching namespace filter."""
        norm_cat = normalize_title(category)
        placeholders = ",".join("?" for _ in namespaces)
        sql = f"""
            SELECT cm.page_id
            FROM category_membership cm
            JOIN pages p ON cm.page_id = p.page_id
            WHERE cm.category = ? AND p.page_namespace IN ({placeholders})
        """
        params = [norm_cat, *namespaces]
        cursor = self._conn.execute(sql, params)
        return [row["page_id"] for row in cursor.fetchall()]

    def categories_of_page(self, page_id: int) -> list[str]:
        """Return list of category names assigned to page_id."""
        cursor = self._conn.execute(
            "SELECT category FROM category_membership WHERE page_id = ?",
            (page_id,),
        )
        return [row["category"] for row in cursor.fetchall()]

    def category_exists(self, category: str) -> bool:
        """Return True if category exists in index."""
        norm_cat = normalize_title(category)
        cursor = self._conn.execute(
            "SELECT 1 FROM categories WHERE category = ? LIMIT 1",
            (norm_cat,),
        )
        return cursor.fetchone() is not None

    def page_by_title(self, title: str) -> PageRow | None:
        """Return PageRow for normalized title or None."""
        norm_title = normalize_title(title)
        cursor = self._conn.execute(
            "SELECT page_id, page_namespace, title, is_redirect FROM pages WHERE title = ?",
            (norm_title,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return PageRow(
            page_id=row["page_id"],
            page_namespace=row["page_namespace"],
            page_title=row["title"],
            page_is_redirect=row["is_redirect"],
        )

    def pages_by_ids(self, ids: Sequence[int]) -> list[PageRow]:
        """Return list of PageRows for given list of page IDs."""
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        sql = (
            f"SELECT page_id, page_namespace, title, is_redirect FROM pages "
            f"WHERE page_id IN ({placeholders})"
        )
        cursor = self._conn.execute(sql, list(ids))
        return [
            PageRow(
                page_id=r["page_id"],
                page_namespace=r["page_namespace"],
                page_title=r["title"],
                page_is_redirect=r["is_redirect"],
            )
            for r in cursor.fetchall()
        ]

    def search_categories(self, query: str, limit: int = 25) -> list[CategoryHit]:
        """Substring category search ranked by exact-match first, then direct_page_count desc."""
        norm_query = normalize_title(query)
        sql = """
            SELECT
                c.category,
                COUNT(DISTINCT cm.page_id) AS direct_page_count,
                COUNT(DISTINCT ce.child_category) AS subcat_count
            FROM categories c
            LEFT JOIN category_membership cm ON c.category = cm.category
            LEFT JOIN category_edges ce ON c.category = ce.parent_category
            WHERE c.category LIKE ?
            GROUP BY c.category
            ORDER BY
                CASE WHEN c.category = ? THEN 0 ELSE 1 END,
                direct_page_count DESC,
                c.category ASC
            LIMIT ?
        """
        pattern = f"%{norm_query}%"
        cursor = self._conn.execute(sql, (pattern, norm_query, limit))

        return [
            CategoryHit(
                category=r["category"],
                direct_page_count=r["direct_page_count"],
                subcat_count=r["subcat_count"],
            )
            for r in cursor.fetchall()
        ]

    def stats(self) -> MetadataStats:
        """Return dataset statistics and build metadata."""
        p_count = self._conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        c_count = self._conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        e_count = self._conn.execute("SELECT COUNT(*) FROM category_edges").fetchone()[0]

        meta_cursor = self._conn.execute("SELECT key, value FROM meta")
        meta_dict = dict(meta_cursor.fetchall())

        return MetadataStats(
            page_count=p_count,
            category_count=c_count,
            edge_count=e_count,
            source_fingerprint=meta_dict.get("source_fingerprint", ""),
            built_at=meta_dict.get("built_at", ""),
        )

    def record_domain_decision(
        self,
        domain_hash: str,
        source_fingerprint: str,
        category: str,
        decision: BranchDecision,
        confidence: float | None,
        reason: str,
        root: str | None,
        depth: int | None,
        source: str,
        decision_at: str,
    ) -> None:
        """Record domain category decision in domain_decisions table (opens write connection)."""
        norm_cat = normalize_title(category)
        write_conn = sqlite3.connect(self.db_path)
        try:
            write_conn.execute(
                """
                INSERT OR REPLACE INTO domain_decisions (
                    domain_hash, source_fingerprint, category, decision, confidence,
                    reason, root, depth, source, decision_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    domain_hash,
                    source_fingerprint,
                    norm_cat,
                    str(decision),
                    confidence,
                    reason,
                    root,
                    depth,
                    source,
                    decision_at,
                ),
            )
            write_conn.commit()
        finally:
            write_conn.close()

    def get_domain_decisions(
        self, domain_hash: str, source_fingerprint: str
    ) -> list[dict[str, Any]]:
        """Retrieve stored domain category decisions."""
        cursor = self._conn.execute(
            """
            SELECT category, decision, confidence, reason, root, depth, source, decision_at
            FROM domain_decisions
            WHERE domain_hash = ? AND source_fingerprint = ?
        """,
            (domain_hash, source_fingerprint),
        )
        return [dict(r) for r in cursor.fetchall()]
