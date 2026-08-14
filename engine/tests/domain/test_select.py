from pathlib import Path

import pytest

from corpussieve.contracts.domain import DomainDefinition, DomainPolicy, DomainRoot
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.manifest import ManifestRecord, SelectionReason
from corpussieve.domain.manifest_io import read_manifest, write_manifest
from corpussieve.domain.resolve import ResolvedRoot
from corpussieve.domain.select import select_articles
from corpussieve.domain.traverse import traverse
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


def test_select_articles_basic(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]
    trav = traverse(fixwiki_idx, roots, set(), set(), defn)

    recs, warnings = select_articles(fixwiki_idx, trav, defn)
    assert len(recs) > 0
    mario = next((r for r in recs if r.title == "Super_Mario_Bros"), None)
    assert mario is not None
    assert mario.page_id == 1


def test_select_articles_forced_and_hard_precedence(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
        forced_include_pages=["Forced_Test_Page", "Super_Mario_Bros"],
        hard_exclude_pages=["Super_Mario_Bros", "Hard_Excluded_Page"],
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]
    trav = traverse(fixwiki_idx, roots, set(), set(), defn)

    recs, warnings = select_articles(fixwiki_idx, trav, defn)
    mario = next((r for r in recs if r.title == "Super_Mario_Bros"), None)
    assert mario is None
    assert any("exclude_overrides_force:Super_Mario_Bros" in w for w in warnings)


def test_select_articles_redirect_policy(fixwiki_idx: MetadataIndex) -> None:
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]

    defn_no_red = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
        policy=DomainPolicy(include_redirects=False),
    )
    trav_no_red = traverse(fixwiki_idx, roots, set(), set(), defn_no_red)
    recs_no_red, _ = select_articles(fixwiki_idx, trav_no_red, defn_no_red)

    defn_red = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
        policy=DomainPolicy(include_redirects=True),
    )
    trav_red = traverse(fixwiki_idx, roots, set(), set(), defn_red)
    recs_red, _ = select_articles(fixwiki_idx, trav_red, defn_red)

    assert len(recs_red) >= len(recs_no_red)


def test_select_articles_runaway_growth(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
        policy=DomainPolicy(max_total_articles=1),
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]
    trav = traverse(fixwiki_idx, roots, set(), set(), defn)

    with pytest.raises(CorpusSieveError) as exc_info:
        select_articles(fixwiki_idx, trav, defn)
    assert exc_info.value.code == ErrorCode.DOMAIN_RUNAWAY_GROWTH


def test_manifest_io_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl.zst"
    records = [
        ManifestRecord(
            project="vg",
            language="en",
            page_id=1,
            title="Super_Mario_Bros",
            namespace=0,
            selected=True,
            selection=SelectionReason(
                root="Category:Video games",
                depth=1,
                via_category="Video_games",
                reason_type="category_path",
            ),
        ),
        ManifestRecord(
            project="vg",
            language="en",
            page_id=2,
            title="Zelda",
            namespace=0,
            selected=True,
            selection=SelectionReason(
                root="Category:Zelda",
                depth=0,
                via_category="Zelda",
                reason_type="forced_include",
            ),
        ),
    ]

    write_manifest(records, path)
    assert path.exists()

    loaded = read_manifest(path)
    assert len(loaded) == 2
    assert loaded[0].title == "Super_Mario_Bros"
    assert loaded[1].title == "Zelda"
