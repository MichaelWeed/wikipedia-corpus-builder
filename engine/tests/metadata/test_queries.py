import sqlite3
from pathlib import Path

import pytest

from corpussieve.contracts.enums import BranchDecision
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


@pytest.fixture
def fixwiki_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "cache" / "metadata.sqlite"
    adapter = WikimediaXmlDumpAdapter(FIXWIKI_DIR)
    build_metadata_index(adapter, db_path)
    return db_path


def test_queries_basic(fixwiki_db: Path) -> None:
    with MetadataIndex(fixwiki_db) as idx:
        assert idx.category_exists("Video_games") is True
        assert idx.category_exists("Non_Existent_Cat") is False

        child_cats = idx.child_categories("Video_games")
        assert any("Platform_games" in c for c in child_cats)

        member_ids = idx.member_page_ids("Video_games")
        assert len(member_ids) > 0

        mario = idx.page_by_title("Super_Mario_Bros")
        assert mario is not None
        assert mario.page_id == 1

        pages = idx.pages_by_ids([1])
        assert len(pages) == 1
        assert pages[0].page_title == "Super_Mario_Bros"

        cats = idx.categories_of_page(1)
        assert "Video_games" in cats or "Platform_games" in cats


def test_search_categories_ranking(fixwiki_db: Path) -> None:
    with MetadataIndex(fixwiki_db) as idx:
        hits = idx.search_categories("Video_games", limit=10)
        assert len(hits) > 0
        assert hits[0].category == "Video_games"  # Exact match ranks first


def test_stats(fixwiki_db: Path) -> None:
    with MetadataIndex(fixwiki_db) as idx:
        stats = idx.stats()
        assert stats.page_count > 0
        assert stats.category_count > 0
        assert stats.edge_count > 0
        assert len(stats.source_fingerprint) == 64


def test_read_only_enforcement(fixwiki_db: Path) -> None:
    with MetadataIndex(fixwiki_db) as idx, pytest.raises(sqlite3.OperationalError):
        idx._conn.execute("INSERT INTO categories (category) VALUES ('Test')")


def test_record_and_get_domain_decisions(fixwiki_db: Path) -> None:
    with MetadataIndex(fixwiki_db) as idx:
        idx.record_domain_decision(
            domain_hash="domhash123",
            source_fingerprint="srcfp123",
            category="Video_games",
            decision=BranchDecision.INCLUDE,
            confidence=0.9,
            reason="Root category",
            root="Category:Video games",
            depth=0,
            source="traversal",
            decision_at="2026-08-13T00:00:00Z",
        )

        decisions = idx.get_domain_decisions("domhash123", "srcfp123")
        assert len(decisions) == 1
        assert decisions[0]["category"] == "Video_games"
        assert decisions[0]["decision"] == "include"
