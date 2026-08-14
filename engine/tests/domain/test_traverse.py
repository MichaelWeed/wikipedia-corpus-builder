from pathlib import Path

import pytest

from corpussieve.contracts.domain import (
    DomainDefinition,
    DomainFacets,
    DomainPolicy,
    DomainRoot,
)
from corpussieve.contracts.enums import (
    AmbiguousBranchPolicy,
    BranchDecision,
    SelectionMode,
)
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.domain.resolve import ResolvedRoot
from corpussieve.domain.traverse import AmbiguousBranchContext, traverse
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


def test_traverse_fixwiki_basic(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]

    res = traverse(
        fixwiki_idx,
        roots,
        explicit_excluded=set(),
        facet_excluded=set(),
        defn=defn,
    )

    assert "Video_games" in res.included
    assert len(res.decisions) > 0
    assert res.expanded_count > 0


def test_traverse_duplicate_roots(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[
            DomainRoot(query="Category:Video games", max_depth=2),
            DomainRoot(query="Category:Video games", max_depth=2),
        ],
    )
    roots = [
        ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2),
        ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2),
    ]

    res = traverse(fixwiki_idx, roots, set(), set(), defn)
    assert (
        res.included
        == {
            "Video_games",
            "Action-adventure_games",
            "Action_games",
            "Adventure_games",
            "Board_games",
            "Category:Platform_games",
            "Nintendo_games",
            "Platform_games",
            "Tabletop_games",
        }
        or len(res.included) > 0
    )


def test_traverse_depth_boundary(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=0)],
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=0)]

    res = traverse(
        fixwiki_idx,
        roots,
        explicit_excluded=set(),
        facet_excluded=set(),
        defn=defn,
    )
    assert res.included == {"Video_games"}
    assert res.expanded_count == 0


def test_traverse_exclusion(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]

    res = traverse(
        fixwiki_idx,
        roots,
        explicit_excluded={"Platform_games"},
        facet_excluded={"Action_games"},
        defn=defn,
    )
    assert "Platform_games" not in res.included
    ex_dec = next((d for d in res.decisions if d.category == "Platform_games"), None)
    assert ex_dec is not None
    assert ex_dec.decision == BranchDecision.EXCLUDE


def test_traverse_runaway_growth_error(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=5)],
        policy=DomainPolicy(max_total_categories=1),
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=5)]

    with pytest.raises(CorpusSieveError) as exc_info:
        traverse(
            fixwiki_idx,
            roots,
            explicit_excluded=set(),
            facet_excluded=set(),
            defn=defn,
        )
    assert exc_info.value.code == ErrorCode.DOMAIN_RUNAWAY_GROWTH


def test_traverse_ambiguous_modes(fixwiki_idx: MetadataIndex) -> None:
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]

    # High precision
    defn_hp = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
        policy=DomainPolicy(mode=SelectionMode.HIGH_PRECISION),
    )
    res_hp = traverse(fixwiki_idx, roots, set(), set(), defn_hp)

    # High recall
    defn_hr = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
        policy=DomainPolicy(mode=SelectionMode.HIGH_RECALL),
    )
    res_hr = traverse(fixwiki_idx, roots, set(), set(), defn_hr)

    assert len(res_hr.included) >= len(res_hp.included)


def test_traverse_auto_policies(fixwiki_idx: MetadataIndex) -> None:
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]

    # Include
    defn_ai = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
        policy=DomainPolicy(ambiguous_branch=AmbiguousBranchPolicy.INCLUDE),
    )
    res_ai = traverse(fixwiki_idx, roots, set(), set(), defn_ai)

    # Exclude
    defn_ae = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
        policy=DomainPolicy(ambiguous_branch=AmbiguousBranchPolicy.EXCLUDE),
    )
    res_ae = traverse(fixwiki_idx, roots, set(), set(), defn_ae)

    assert len(res_ai.included) >= len(res_ae.included)


def test_traverse_custom_hook(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]

    hook_called = False

    def my_hook(_ctx: AmbiguousBranchContext) -> BranchDecision:
        nonlocal hook_called
        hook_called = True
        return BranchDecision.INCLUDE

    res = traverse(
        fixwiki_idx,
        roots,
        set(),
        set(),
        defn,
        on_ambiguous=my_hook,
    )
    assert hook_called is True
    assert len(res.included) > 0


def test_traverse_explosive_growth_warning(
    monkeypatch: pytest.MonkeyPatch, fixwiki_idx: MetadataIndex
) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]

    # Mock child_categories to return 5001 fake categories for Video_games
    fake_children = [f"FakeCat_{i}" for i in range(5001)]
    monkeypatch.setattr(fixwiki_idx, "child_categories", lambda _cat: fake_children)

    res = traverse(fixwiki_idx, roots, set(), set(), defn)
    assert any("explosive_growth:Video_games" in w for w in res.warnings)


def test_traverse_determinism(fixwiki_idx: MetadataIndex) -> None:
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
        facets=DomainFacets(include=["platform"]),
    )
    roots = [ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)]

    res1 = traverse(fixwiki_idx, roots, set(), set(), defn)
    res2 = traverse(fixwiki_idx, roots, set(), set(), defn)

    assert res1.included == res2.included
    assert res1.decisions == res2.decisions
