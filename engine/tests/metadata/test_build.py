import sqlite3
import time
from pathlib import Path

from corpussieve.metadata.build import build_metadata_index
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_build_metadata_index_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "cache" / "metadata.sqlite"
    adapter = WikimediaXmlDumpAdapter(FIXWIKI_DIR)

    t0 = time.time()
    build_metadata_index(adapter, db_path)
    t1 = time.time()

    # DoD requirement: fixwiki index builds in < 5 s
    assert (t1 - t0) < 5.0
    assert db_path.exists()
    assert not db_path.with_name(db_path.name + ".building").exists()

    conn = sqlite3.connect(db_path)
    try:
        # Check meta table
        meta_rows = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        assert meta_rows.get("schema_version") == "1"
        assert len(meta_rows.get("source_fingerprint", "")) == 64

        # Check pages count
        pages_count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        assert pages_count > 0

        # Check categories count
        categories_count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        assert categories_count > 0

        # Check Video_games category exists
        vg_cat = conn.execute(
            "SELECT category FROM categories WHERE category = 'Video_games'"
        ).fetchone()
        assert vg_cat is not None
    finally:
        conn.close()


def test_build_metadata_index_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "cache" / "metadata.sqlite"
    adapter = WikimediaXmlDumpAdapter(FIXWIKI_DIR)

    build_metadata_index(adapter, db_path)
    time.sleep(0.01)
    build_metadata_index(adapter, db_path)
    assert db_path.exists()
