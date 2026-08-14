from pathlib import Path

import pytest

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.extraction.multistream_index import (
    group_selected,
    iter_index,
)

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_iter_index_fixwiki() -> None:
    idx_file = FIXWIKI_DIR / "fixwiki-20260801-pages-articles-multistream-index.txt.bz2"
    entries = list(iter_index(idx_file))
    assert len(entries) > 0
    assert entries[0].offset >= 0
    assert entries[0].page_id > 0


def test_group_selected_fixwiki() -> None:
    idx_file = FIXWIKI_DIR / "fixwiki-20260801-pages-articles-multistream-index.txt.bz2"
    entries = list(iter_index(idx_file))
    selected = {entries[0].page_id, entries[1].page_id}

    plan = group_selected(idx_file, selected)
    assert len(plan.groups) > 0
    assert len(plan.missing_ids) == 0


def test_group_selected_missing_id() -> None:
    idx_file = FIXWIKI_DIR / "fixwiki-20260801-pages-articles-multistream-index.txt.bz2"
    plan = group_selected(idx_file, {99999999})
    assert len(plan.groups) == 0
    assert plan.missing_ids == [99999999]


def test_iter_index_malformed(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.txt"
    bad_file.write_text("invalid_line_without_colons\n", encoding="utf-8")
    with pytest.raises(CorpusSieveError) as exc_info:
        list(iter_index(bad_file))
    assert exc_info.value.code == ErrorCode.EXTRACTION_PARSE_FAILED
