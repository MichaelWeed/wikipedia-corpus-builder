from pathlib import Path

from corpussieve.extraction.multistream import extract_multistream
from corpussieve.extraction.multistream_index import iter_index

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_extract_multistream_fixwiki() -> None:
    dump_file = FIXWIKI_DIR / "fixwiki-20260801-pages-articles-multistream.xml.bz2"
    index_file = FIXWIKI_DIR / "fixwiki-20260801-pages-articles-multistream-index.txt.bz2"

    entries = list(iter_index(index_file))
    target_ids = {entries[0].page_id, entries[1].page_id}

    extracted = list(extract_multistream(dump_file, index_file, target_ids))
    assert len(extracted) == len(target_ids)
    extracted_ids = {p.page_id for p in extracted}
    assert extracted_ids == target_ids
    assert len(extracted[0].wikitext) > 0
