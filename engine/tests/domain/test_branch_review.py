from pathlib import Path

import pytest
import respx

from corpussieve.contracts.domain import DomainDefinition, DomainRoot
from corpussieve.contracts.enums import BranchDecision
from corpussieve.domain.branch_review import LlmAmbiguousHook
from corpussieve.domain.definition import domain_hash
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.models.ollama import OLLAMA_DEFAULT_URL, OllamaProvider
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


def test_llm_ambiguous_hook_cache(
    fixwiki_setup: tuple[MetadataIndex, DomainDefinition, str],
    respx_mock: respx.MockRouter,
) -> None:
    idx, defn, fp = fixwiki_setup
    from corpussieve.contracts.providers import ProviderEndpoint

    provider = OllamaProvider(
        ProviderEndpoint(provider="ollama", base_url=OLLAMA_DEFAULT_URL, is_loopback=True)
    )

    # Pre-populate cache in SQLite
    d_hash = domain_hash(defn)
    from datetime import UTC, datetime

    now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    idx.record_domain_decision(
        domain_hash=d_hash,
        source_fingerprint=fp,
        category="Category:Board_games",
        decision=BranchDecision.EXCLUDE,
        confidence=1.0,
        reason="Cached exclusion",
        root="Category:Video games",
        depth=1,
        source="llm",
        decision_at=now_iso,
    )

    from corpussieve.domain.resolve import ResolvedRoot
    from corpussieve.domain.traverse import AmbiguousBranchContext

    r_root = ResolvedRoot(query="Category:Video games", category="Video_games", max_depth=2)
    ctx = AmbiguousBranchContext(
        defn=defn,
        root=r_root,
        parent_path=["Video_games"],
        candidate="Category:Board_games",
        sample_children=[],
        sample_members=[],
    )

    hook = LlmAmbiguousHook(provider, "llama3:latest", idx, defn, fp)
    dec = hook(ctx)

    assert dec == BranchDecision.EXCLUDE
    # Ensure zero HTTP requests were made because cache hit
    assert len(respx_mock.calls) == 0
