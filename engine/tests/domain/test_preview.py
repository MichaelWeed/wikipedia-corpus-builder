from pathlib import Path

import pytest

from corpussieve.contracts.domain import DomainDefinition, DomainRoot
from corpussieve.domain.lock_build import compile_lock
from corpussieve.domain.preview import build_preview, explain_page
from corpussieve.domain.select import select_articles
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


@pytest.fixture
def fixwiki_setup(tmp_path: Path) -> tuple[MetadataIndex, DomainDefinition, str]:
    db_path = tmp_path / "cache" / "metadata.sqlite"
    adapter = WikimediaXmlDumpAdapter(FIXWIKI_DIR)
    build_metadata_index(adapter, db_path)
    idx = MetadataIndex(db_path)
    fp = adapter.inspect().fingerprint.fingerprint

    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )

    return idx, defn, fp


def test_build_preview_basic(fixwiki_setup: tuple[MetadataIndex, DomainDefinition, str]) -> None:
    idx, defn, fp = fixwiki_setup
    lock, trav = compile_lock(defn, idx, fp)
    records, _ = select_articles(idx, trav, defn)

    prev = build_preview(idx, lock, trav, records, defn)
    assert prev.article_count == len(records)
    assert prev.estimated_output_bytes > 0
    assert len(prev.sample_included) <= 10


def test_explain_page_included(fixwiki_setup: tuple[MetadataIndex, DomainDefinition, str]) -> None:
    idx, defn, fp = fixwiki_setup
    lock, trav = compile_lock(defn, idx, fp)
    records, _ = select_articles(idx, trav, defn)

    res = explain_page(idx, lock, records, "Super_Mario_Bros", defn)
    assert res.status == "included"
    assert res.target == "Super_Mario_Bros"
    assert len(res.provenance_chain) > 0


def test_explain_page_absent(fixwiki_setup: tuple[MetadataIndex, DomainDefinition, str]) -> None:
    idx, defn, fp = fixwiki_setup
    lock, trav = compile_lock(defn, idx, fp)
    records, _ = select_articles(idx, trav, defn)

    res = explain_page(idx, lock, records, "Completely_Absent_Article_Name", defn)
    assert res.status == "absent"


def test_explain_page_excluded(fixwiki_setup: tuple[MetadataIndex, DomainDefinition, str]) -> None:
    idx, defn, fp = fixwiki_setup
    defn.hard_exclude_pages = ["Super_Mario_Bros"]
    lock, trav = compile_lock(defn, idx, fp)
    records, _ = select_articles(idx, trav, defn)

    res = explain_page(idx, lock, records, "Super_Mario_Bros", defn)
    assert res.status == "excluded"
    assert "Hard excluded" in res.reason
