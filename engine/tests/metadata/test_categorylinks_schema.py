"""Coverage for the categorylinks schema migration (cl_to -> cl_target_id/linktarget).

Real Wikimedia dumps (2026) use the "current" schema: categorylinks.cl_target_id
references linktarget.lt_id rather than inlining the category title as cl_to.
The existing fixwiki golden fixtures use the legacy schema and continue to
exercise that path unchanged (see tests/metadata/test_build.py). This file adds
small, inline-constructed dumps for the current schema so both paths have
direct regression coverage without maintaining two full binary fixture sets.
"""

import gzip
import sqlite3
from pathlib import Path

import pytest

from corpussieve.contracts.enums import MemberType
from corpussieve.contracts.errors import CorpusSieveError
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.rows import (
    detect_categorylinks_schema,
    iter_categorylinks_rows,
    iter_linktarget_rows,
)
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter


def _gz(text: str) -> bytes:
    return gzip.compress(text.encode("utf-8"), mtime=0)


CURRENT_CL_SQL = (
    "DROP TABLE IF EXISTS `categorylinks`;\n"
    "CREATE TABLE `categorylinks` (\n"
    "  `cl_from` int(8) unsigned NOT NULL DEFAULT 0,\n"
    "  `cl_sortkey` varbinary(230) NOT NULL DEFAULT '',\n"
    "  `cl_timestamp` timestamp NOT NULL DEFAULT current_timestamp(),\n"
    "  `cl_sortkey_prefix` varbinary(255) NOT NULL DEFAULT '',\n"
    "  `cl_type` enum('page','subcat','file') NOT NULL DEFAULT 'page',\n"
    "  `cl_collation_id` smallint(5) unsigned NOT NULL DEFAULT 0,\n"
    "  `cl_target_id` bigint(20) unsigned NOT NULL,\n"
    "  PRIMARY KEY (`cl_from`,`cl_target_id`)\n"
    ") ENGINE=InnoDB DEFAULT CHARSET=binary;\n"
    "INSERT INTO `categorylinks` VALUES "
    "(101,'','2026-08-01 00:00:00','','page',1,900),"
    "(102,'','2026-08-01 00:00:00','','page',1,900),"
    "(50,'','2026-08-01 00:00:00','','subcat',1,900);\n"
)

LEGACY_CL_SQL = (
    "DROP TABLE IF EXISTS `categorylinks`;\n"
    "CREATE TABLE `categorylinks` (\n"
    "  `cl_from` int(10) unsigned NOT NULL DEFAULT '0',\n"
    "  `cl_to` varbinary(255) NOT NULL DEFAULT '',\n"
    "  `cl_sortkey` varbinary(230) NOT NULL DEFAULT '',\n"
    "  `cl_timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,\n"
    "  `cl_sortkey_prefix` varbinary(255) NOT NULL DEFAULT '',\n"
    "  `cl_collation` varbinary(32) NOT NULL DEFAULT '',\n"
    "  `cl_type` enum('page','subcat','file') NOT NULL DEFAULT 'page',\n"
    "  PRIMARY KEY (`cl_from`,`cl_to`)\n"
    ") ENGINE=InnoDB DEFAULT CHARSET=binary;\n"
    "INSERT INTO `categorylinks` VALUES "
    "(101,'Video_games','','2026-08-01 00:00:00','','uppercase','page');\n"
)

LINKTARGET_SQL = (
    "DROP TABLE IF EXISTS `linktarget`;\n"
    "CREATE TABLE `linktarget` (\n"
    "  `lt_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,\n"
    "  `lt_namespace` int(11) NOT NULL,\n"
    "  `lt_title` varbinary(255) NOT NULL,\n"
    "  PRIMARY KEY (`lt_id`)\n"
    ") ENGINE=InnoDB;\n"
    "INSERT INTO `linktarget` VALUES "
    "(900,14,'Video_games'),(901,0,'Some_Article_Link');\n"
)


def test_detect_categorylinks_schema_current(tmp_path: Path) -> None:
    p = tmp_path / "categorylinks.sql.gz"
    p.write_bytes(_gz(CURRENT_CL_SQL))
    columns, is_current = detect_categorylinks_schema(p)
    assert is_current is True
    assert "cl_target_id" in columns
    assert "cl_to" not in columns


def test_detect_categorylinks_schema_legacy(tmp_path: Path) -> None:
    p = tmp_path / "categorylinks.sql.gz"
    p.write_bytes(_gz(LEGACY_CL_SQL))
    columns, is_current = detect_categorylinks_schema(p)
    assert is_current is False
    assert "cl_to" in columns


def test_iter_categorylinks_rows_current_schema_yields_target_id(tmp_path: Path) -> None:
    p = tmp_path / "categorylinks.sql.gz"
    p.write_bytes(_gz(CURRENT_CL_SQL))
    rows = list(iter_categorylinks_rows(p))
    assert len(rows) == 3
    assert rows[0].cl_from == 101
    assert rows[0].cl_to is None
    assert rows[0].cl_target_id == 900
    assert rows[0].cl_type == MemberType.PAGE
    assert rows[2].cl_type == MemberType.SUBCAT


def test_iter_categorylinks_rows_legacy_schema_yields_cl_to(tmp_path: Path) -> None:
    p = tmp_path / "categorylinks.sql.gz"
    p.write_bytes(_gz(LEGACY_CL_SQL))
    rows = list(iter_categorylinks_rows(p))
    assert len(rows) == 1
    assert rows[0].cl_to == "Video_games"
    assert rows[0].cl_target_id is None


def test_iter_linktarget_rows(tmp_path: Path) -> None:
    p = tmp_path / "linktarget.sql.gz"
    p.write_bytes(_gz(LINKTARGET_SQL))
    rows = list(iter_linktarget_rows(p))
    assert len(rows) == 2
    cat_rows = [r for r in rows if r.lt_namespace == 14]
    assert len(cat_rows) == 1
    assert cat_rows[0].lt_id == 900
    assert cat_rows[0].lt_title == "Video_games"


def _write_minimal_current_schema_dump(project_root: Path) -> Path:
    """Build a tiny synthetic dump directory using the CURRENT categorylinks schema."""
    d = project_root / "source"
    d.mkdir(parents=True)

    page_sql = (
        "DROP TABLE IF EXISTS `page`;\n"
        "CREATE TABLE `page` (\n"
        "  `page_id` int(10) unsigned NOT NULL AUTO_INCREMENT,\n"
        "  `page_namespace` int(11) NOT NULL DEFAULT '0',\n"
        "  `page_title` varbinary(255) NOT NULL DEFAULT '',\n"
        "  `page_restrictions` tinyblob NOT NULL,\n"
        "  `page_is_redirect` tinyint(3) unsigned NOT NULL DEFAULT '0',\n"
        "  PRIMARY KEY (`page_id`)\n"
        ") ENGINE=InnoDB DEFAULT CHARSET=binary;\n"
        "INSERT INTO `page` VALUES "
        "(101,0,'Example_Game',b'',0),"
        "(102,0,'Another_Game',b'',0),"
        "(50,14,'Video_games',b'',0);\n"
    )
    (d / "curwiki-20260801-page.sql.gz").write_bytes(_gz(page_sql))
    (d / "curwiki-20260801-categorylinks.sql.gz").write_bytes(_gz(CURRENT_CL_SQL))
    (d / "curwiki-20260801-linktarget.sql.gz").write_bytes(_gz(LINKTARGET_SQL))

    xml = (
        '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">\n'
        "<page><title>Example_Game</title><ns>0</ns><id>101</id>"
        "<revision><id>1</id><text>Example game text.</text></revision></page>\n"
        "</mediawiki>\n"
    )
    import bz2

    (d / "curwiki-20260801-pages-articles.xml.bz2").write_bytes(bz2.compress(xml.encode("utf-8")))
    return d


def test_build_metadata_index_current_schema_end_to_end(tmp_path: Path) -> None:
    """The exact real-world regression: current-schema categorylinks + linktarget
    must resolve to non-empty category_edges/category_membership."""
    source_dir = _write_minimal_current_schema_dump(tmp_path)
    db_path = tmp_path / "cache" / "metadata.sqlite"
    adapter = WikimediaXmlDumpAdapter(source_dir)

    build_metadata_index(adapter, db_path)

    conn = sqlite3.connect(db_path)
    try:
        edges = conn.execute(
            "SELECT parent_category, child_category FROM category_edges"
        ).fetchall()
        membership = conn.execute("SELECT category, page_id FROM category_membership").fetchall()
        assert edges == [("Video_games", "Video_games")] or len(edges) == 1
        assert set(membership) == {("Video_games", 101), ("Video_games", 102)}
    finally:
        conn.close()


def test_build_metadata_index_missing_linktarget_raises(tmp_path: Path) -> None:
    """Current-schema categorylinks without a companion linktarget must fail
    with a clear, actionable error -- not silently produce an empty graph."""
    source_dir = _write_minimal_current_schema_dump(tmp_path)
    (source_dir / "curwiki-20260801-linktarget.sql.gz").unlink()

    db_path = tmp_path / "cache" / "metadata.sqlite"
    adapter = WikimediaXmlDumpAdapter(source_dir)

    with pytest.raises(CorpusSieveError) as exc_info:
        build_metadata_index(adapter, db_path)
    assert "linktarget" in str(exc_info.value).lower()


def test_build_metadata_index_fails_loudly_on_stale_linktarget(tmp_path: Path) -> None:
    """A non-trivial categorylinks file that resolves to zero categories (e.g.
    linktarget from a different dump date) must raise, not silently succeed
    with an empty graph -- this is the exact real-world failure mode."""
    source_dir = _write_minimal_current_schema_dump(tmp_path)

    # Build a categorylinks file with >=1000 rows all referencing a
    # cl_target_id absent from linktarget.sql.gz.
    values = ",".join(
        f"({100 + i},'','2026-08-01 00:00:00','','page',1,{99000 + i})" for i in range(1200)
    )
    stale_cl_sql = (
        CURRENT_CL_SQL.split("INSERT INTO")[0] + f"INSERT INTO `categorylinks` VALUES {values};\n"
    )
    (source_dir / "curwiki-20260801-categorylinks.sql.gz").write_bytes(_gz(stale_cl_sql))

    db_path = tmp_path / "cache" / "metadata.sqlite"
    adapter = WikimediaXmlDumpAdapter(source_dir)

    with pytest.raises(CorpusSieveError) as exc_info:
        build_metadata_index(adapter, db_path)
    assert "resolved 0" in str(exc_info.value)
