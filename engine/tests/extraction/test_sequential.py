from pathlib import Path

from corpussieve.extraction.multistream import extract_multistream
from corpussieve.extraction.multistream_index import iter_index
from corpussieve.extraction.sequential import extract_sequential

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_extract_sequential_fixwiki() -> None:
    dump_file = FIXWIKI_DIR / "fixwiki-20260801-pages-articles-multistream.xml.bz2"
    index_file = FIXWIKI_DIR / "fixwiki-20260801-pages-articles-multistream-index.txt.bz2"

    entries = list(iter_index(index_file))
    target_ids = {entries[0].page_id, entries[1].page_id}

    ms_pages = list(extract_multistream(dump_file, index_file, target_ids))
    seq_pages = list(extract_sequential(dump_file, target_ids))

    assert len(seq_pages) == len(ms_pages)
    ms_map = {p.page_id: p.wikitext for p in ms_pages}
    seq_map = {p.page_id: p.wikitext for p in seq_pages}

    assert ms_map == seq_map
