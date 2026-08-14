import bz2
import gzip
import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixwiki"


def test_fixwiki_files_exist() -> None:
    expected_files = [
        "fixwiki-20260801-pages-articles-multistream.xml.bz2",
        "fixwiki-20260801-pages-articles-multistream-index.txt.bz2",
        "fixwiki-20260801-pages-articles.xml.bz2",
        "fixwiki-20260801-page.sql.gz",
        "fixwiki-20260801-categorylinks.sql.gz",
        "expected.json",
    ]
    for filename in expected_files:
        p = FIXTURE_DIR / filename
        assert p.exists()
        assert p.stat().st_size > 0


def test_fixwiki_xml_and_index_validity() -> None:
    multistream_xml_bz2 = FIXTURE_DIR / "fixwiki-20260801-pages-articles-multistream.xml.bz2"
    index_bz2 = FIXTURE_DIR / "fixwiki-20260801-pages-articles-multistream-index.txt.bz2"

    index_text = bz2.decompress(index_bz2.read_bytes()).decode("utf-8")
    lines = index_text.strip().split("\n")
    assert len(lines) > 0

    first_line = lines[0]
    offset_str, page_id_str, title = first_line.split(":", 2)
    offset = int(offset_str)
    assert offset >= 0
    assert int(page_id_str) > 0
    assert len(title) > 0

    # Decompress stream at offset from multistream xml bz2
    with multistream_xml_bz2.open("rb") as f:
        f.seek(offset)
        stream_data = f.read()
        decompressed_chunk = bz2.decompress(stream_data).decode("utf-8")
        assert title in decompressed_chunk


def test_fixwiki_sql_dumps() -> None:
    page_sql_gz = FIXTURE_DIR / "fixwiki-20260801-page.sql.gz"
    cl_sql_gz = FIXTURE_DIR / "fixwiki-20260801-categorylinks.sql.gz"

    page_sql = gzip.decompress(page_sql_gz.read_bytes()).decode("utf-8")
    assert "INSERT INTO `page` VALUES" in page_sql
    assert "Super_Mario_Bros" in page_sql

    cl_sql = gzip.decompress(cl_sql_gz.read_bytes()).decode("utf-8")
    assert "INSERT INTO `categorylinks` VALUES" in cl_sql
    assert "Video_games" in cl_sql


def test_fixwiki_expected_ground_truth() -> None:
    expected_path = FIXTURE_DIR / "expected.json"
    data = json.loads(expected_path.read_text(encoding="utf-8"))
    assert "video_games_domain" in data
    assert "Super_Mario_Bros" in data["video_games_domain"]["selected_pages"]
