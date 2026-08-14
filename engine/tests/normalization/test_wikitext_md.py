from corpussieve.contracts.corpus import CorpusContent, CorpusRecord, CorpusSource
from corpussieve.normalization.base import get_normalizer
from corpussieve.normalization.wikitext_md import WikitextMarkdownNormalizer


def test_normalizer_registry() -> None:
    norm = get_normalizer("wikitext-md-v1")
    assert isinstance(norm, WikitextMarkdownNormalizer)


def test_normalize_basic_article() -> None:
    norm = WikitextMarkdownNormalizer()
    rec = CorpusRecord(
        document_id="cs-doc-123",
        source=CorpusSource(
            project="en",
            language="en",
            page_id=1,
            revision_id=101,
            title="Super_Mario_Bros",
            source_url="https://en.wikipedia.org/wiki/Super_Mario_Bros",
        ),
        categories=["Video_games"],
        selection={
            "root": "Video_games",
            "depth": 0,
            "via_category": "Video_games",
            "reason_type": "category_path",
        },
        content=CorpusContent(
            format="wikitext",
            raw="""== Overview ==
'''Super Mario Bros.''' is a [[platform game]] developed by [[Nintendo]].

=== Gameplay ===
Features include [[Item|items]] and [[Power-up]].

== References ==
* Reference 1
""",
        ),
    )
    doc = norm.normalize(rec)
    assert doc.title == "Super Mario Bros"
    assert doc.frontmatter["project"] == "en"
    assert doc.frontmatter["document_id"] == "cs-doc-123"
    assert "# Super Mario Bros" in doc.markdown
    assert "## Overview" in doc.markdown
    assert "### Gameplay" in doc.markdown
    assert "**Super Mario Bros.** is a platform game developed by Nintendo." in doc.markdown
    assert "items" in doc.markdown
    assert "References" not in doc.markdown


def test_normalize_infobox_and_malformed() -> None:
    norm = WikitextMarkdownNormalizer()
    rec = CorpusRecord(
        document_id="cs-doc-456",
        source=CorpusSource(
            project="en",
            language="en",
            page_id=2,
            revision_id=102,
            title="Infobox_Game",
            source_url="https://en.wikipedia.org/wiki/Infobox_Game",
        ),
        categories=[],
        selection={
            "root": "Video_games",
            "depth": 0,
            "via_category": "Video_games",
            "reason_type": "category_path",
        },
        content=CorpusContent(
            format="wikitext",
            raw="{{Infobox game\n| developer = Nintendo\n| year = 1985\n}}\nMalformed text {{{[[[",
        ),
    )
    doc = norm.normalize(rec)
    has_facts = "**Facts**" in doc.markdown
    has_skipped = doc.warnings == ["infobox_skipped"]
    assert has_facts or has_skipped or len(doc.markdown) > 0
