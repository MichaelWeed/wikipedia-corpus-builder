from pathlib import Path

import pytest

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_inspect_fixwiki_multistream_full() -> None:
    adapter = WikimediaXmlDumpAdapter(FIXWIKI_DIR)
    inspection = adapter.inspect()

    assert inspection.adapter == "wikimedia_xml_dump"
    assert inspection.dump_kind == "multistream"
    assert inspection.has_multistream_index is True
    assert inspection.has_page_sql is True
    assert inspection.has_categorylinks_sql is True
    assert len(inspection.warnings) == 0
    assert inspection.fingerprint.project == "fixwiki"
    assert inspection.fingerprint.language == "fix"


def test_inspect_sequential_fallback_and_warnings(tmp_path: Path) -> None:
    # Copy only the multistream XML without index or SQL companions
    src_xml = FIXWIKI_DIR / "fixwiki-20260801-pages-articles-multistream.xml.bz2"
    dst_xml = tmp_path / src_xml.name
    dst_xml.write_bytes(src_xml.read_bytes())

    adapter = WikimediaXmlDumpAdapter(tmp_path)
    inspection = adapter.inspect()

    assert inspection.dump_kind == "sequential"
    assert inspection.has_multistream_index is False
    assert inspection.has_page_sql is False
    assert inspection.has_categorylinks_sql is False
    assert len(inspection.warnings) >= 3


def test_inspect_unsupported_dir(tmp_path: Path) -> None:
    # Empty directory
    adapter = WikimediaXmlDumpAdapter(tmp_path)
    with pytest.raises(CorpusSieveError) as exc_info:
        adapter.inspect()
    assert exc_info.value.code == ErrorCode.SOURCE_UNSUPPORTED
