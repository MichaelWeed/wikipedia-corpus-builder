from pathlib import Path

import pytest

from corpussieve.contracts.domain import DomainDefinition, DomainFacets, DomainRoot
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.domain.resolve import resolve_exclusions, resolve_roots
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


@pytest.fixture
def fixwiki_idx(tmp_path: Path) -> MetadataIndex:
    db_path = tmp_path / "cache" / "metadata.sqlite"
    adapter = WikimediaXmlDumpAdapter(FIXWIKI_DIR)
    build_metadata_index(adapter, db_path)
    return MetadataIndex(db_path)


def test_resolve_roots_success(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=3)],
    )
    res = resolve_roots(defn, fixwiki_idx)
    assert len(res.resolved) == 1
    assert res.resolved[0].category == "Video_games"
    assert res.resolved[0].max_depth == 3


def test_resolve_roots_unresolved_with_candidates(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:NonExistentGamesCat")],
    )
    with pytest.raises(CorpusSieveError) as exc_info:
        resolve_roots(defn, fixwiki_idx)
    assert exc_info.value.code == ErrorCode.DOMAIN_ROOT_UNRESOLVED
    assert "unresolved" in exc_info.value.detail


def test_resolve_exclusions(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games")],
        exclude_categories=["Board_games"],
        facets=DomainFacets(exclude=["tabletop"]),
    )
    explicit, facet = resolve_exclusions(defn, fixwiki_idx)
    assert "Board_games" in explicit
    assert any("tabletop" in c.lower() for c in facet)
