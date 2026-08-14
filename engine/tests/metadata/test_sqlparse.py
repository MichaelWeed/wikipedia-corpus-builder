from pathlib import Path

from corpussieve.contracts.enums import MemberType
from corpussieve.metadata.rows import iter_categorylinks_rows, iter_page_rows
from corpussieve.metadata.sqlparse import iter_insert_tuples
from corpussieve.metadata.titles import normalize_title

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_normalize_title() -> None:
    assert normalize_title(" video games ") == "Video_games"
    assert normalize_title("super mario bros") == "Super_mario_bros"
    assert normalize_title("日本のゲーム") == "日本のゲーム"
    assert normalize_title("") == ""


def test_parse_fixwiki_page_sql() -> None:
    page_sql_path = FIXWIKI_DIR / "fixwiki-20260801-page.sql.gz"
    rows = list(iter_page_rows(page_sql_path))
    assert len(rows) > 0

    mario_row = next((r for r in rows if r.page_title == "Super_Mario_Bros"), None)
    assert mario_row is not None
    assert mario_row.page_id == 1
    assert mario_row.page_namespace == 0
    assert mario_row.page_is_redirect == 0

    redirect_row = next((r for r in rows if r.page_title == "Super_Mario_Bros_Redirect"), None)
    assert redirect_row is not None
    assert redirect_row.page_is_redirect == 1


def test_parse_fixwiki_categorylinks_sql() -> None:
    cl_sql_path = FIXWIKI_DIR / "fixwiki-20260801-categorylinks.sql.gz"
    rows = list(iter_categorylinks_rows(cl_sql_path))
    assert len(rows) > 0

    vg_link = next((r for r in rows if r.cl_from == 1 and r.cl_to == "Video_games"), None)
    assert vg_link is not None
    assert vg_link.cl_type == MemberType.PAGE

    subcat_link = next(
        (r for r in rows if r.cl_to == "Video_games" and r.cl_type == MemberType.SUBCAT),
        None,
    )
    assert subcat_link is not None


def test_small_buffer_parsing() -> None:
    # Test buffer boundary spanning with 64-byte chunks
    cl_sql_path = FIXWIKI_DIR / "fixwiki-20260801-categorylinks.sql.gz"
    normal_rows = list(iter_categorylinks_rows(cl_sql_path, chunk_size=1024 * 1024))
    small_buf_rows = list(iter_categorylinks_rows(cl_sql_path, chunk_size=64))

    assert len(normal_rows) == len(small_buf_rows)
    assert normal_rows == small_buf_rows


def test_adversarial_escaped_strings(tmp_path: Path) -> None:
    import gzip

    sql_content = (
        "INSERT INTO `page` VALUES "
        "(100,0,'Page_with_\\'single_quotes\\'','',0,0,0.5,'20260801000000',NULL,100,50,'wikitext','en'),"
        "(101,0,'Unicode_日本のゲーム','',0,0,0.5,'20260801000000',NULL,101,50,'wikitext','en');\n"
    )
    sql_path = tmp_path / "test-page.sql.gz"
    sql_path.write_bytes(gzip.compress(sql_content.encode("utf-8")))

    tuples = list(iter_insert_tuples(sql_path, "page", chunk_size=32))
    assert len(tuples) == 2
    assert tuples[0][2] == "Page_with_'single_quotes'"
    assert tuples[1][2] == "Unicode_日本のゲーム"
