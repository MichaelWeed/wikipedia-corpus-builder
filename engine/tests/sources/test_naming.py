from corpussieve.sources.wikimedia.naming import parse_dump_filename


def test_parse_valid_dump_filenames() -> None:
    parts1 = parse_dump_filename("enwiki-20260801-pages-articles-multistream.xml.bz2")
    assert parts1 is not None
    assert parts1.project == "enwiki"
    assert parts1.language == "en"
    assert parts1.date == "20260801"
    assert parts1.kind == "pages-articles-multistream.xml.bz2"

    parts2 = parse_dump_filename("fixwiki-20260801-pages-articles-multistream-index.txt.bz2")
    assert parts2 is not None
    assert parts2.project == "fixwiki"
    assert parts2.language == "fix"
    assert parts2.date == "20260801"
    assert parts2.kind == "pages-articles-multistream-index.txt.bz2"

    parts3 = parse_dump_filename("jawiki-20260801-pages-articles.xml.bz2")
    assert parts3 is not None
    assert parts3.project == "jawiki"
    assert parts3.language == "ja"

    parts4 = parse_dump_filename("dewiki-20260801-page.sql.gz")
    assert parts4 is not None
    assert parts4.kind == "page.sql.gz"

    parts5 = parse_dump_filename("frwiki-20260801-categorylinks.sql.gz")
    assert parts5 is not None
    assert parts5.kind == "categorylinks.sql.gz"


def test_parse_invalid_near_misses() -> None:
    # Invalid extension
    assert parse_dump_filename("enwiki-20260801-pages-articles.xml") is None
    # Invalid date format
    assert parse_dump_filename("enwiki-2026-08-01-pages-articles.xml.bz2") is None
    # Random unknown file
    assert parse_dump_filename("readme.txt") is None
    # Misspelled kind
    assert parse_dump_filename("enwiki-20260801-pages.xml.bz2") is None
