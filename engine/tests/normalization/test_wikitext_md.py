from corpussieve.contracts.corpus import CorpusContent, CorpusRecord, CorpusSource
from corpussieve.normalization.base import get_normalizer
from corpussieve.normalization.wikitext_md import WikitextMarkdownNormalizer


def _record(raw: str, title: str = "Infobox_Game", page_id: int = 2) -> CorpusRecord:
    return CorpusRecord(
        document_id=f"cs-doc-{page_id}",
        source=CorpusSource(
            project="simple",
            language="en",
            page_id=page_id,
            revision_id=100 + page_id,
            title=title,
            source_url=f"https://simple.wikipedia.org/wiki/{title}",
        ),
        categories=[],
        selection={
            "root": "Video_games",
            "depth": 0,
            "via_category": "Video_games",
            "reason_type": "category_path",
        },
        content=CorpusContent(format="wikitext", raw=raw),
    )


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


def test_normalize_scalar_infobox_becomes_facts_list() -> None:
    """A plain-value-only infobox converts to the design-§15.1 Facts list.

    Regression for FINDINGS.md #9: this test previously asserted
    `has_facts or has_skipped or len(doc.markdown) > 0`, which is true
    almost regardless of output and would not have caught the bug below.
    """
    norm = WikitextMarkdownNormalizer()
    rec = _record("{{Infobox game\n| developer = Nintendo\n| year = 1985\n}}\nSome body text.")
    doc = norm.normalize(rec)
    assert doc.warnings == []
    assert "**Facts**" in doc.markdown
    assert "- **developer**: Nintendo" in doc.markdown
    assert "- **year**: 1985" in doc.markdown
    assert "Some body text." in doc.markdown


def test_normalize_infobox_with_nested_template_param_does_not_crash() -> None:
    """FINDINGS.md #9 root cause: an infobox param containing a nested
    template (e.g. `{{Start date and age|...}}`, extremely common in real
    infoboxes for release dates) crashed `_convert()` with an unhandled
    `ValueError` from mwparserfromhell's `remove()` on an already-detached
    node -- silently caught by `normalize()`'s broad `except Exception` and
    replaced with a crude character-stripped dump of the *entire* article,
    including leaking template names like "Italic title" as bare text.
    """
    norm = WikitextMarkdownNormalizer()
    rec = _record(
        "{{Italic title}}\n"
        "{{Infobox game\n"
        "| developer = Nintendo\n"
        "| released = {{Start date and age|1985|Jun|1}}\n"
        "}}\n"
        "Some body text about the game.",
    )
    doc = norm.normalize(rec)
    assert doc.warnings == ["infobox_skipped"]
    assert "parse_degraded" not in doc.warnings
    assert "Italic title" not in doc.markdown
    assert "Start date and age" not in doc.markdown
    assert "Some body text about the game." in doc.markdown


def test_normalize_real_pizza_tower_article() -> None:
    """Real simple.wikipedia.org wikitext (fetched 2026-08-15) for the exact
    article named in FINDINGS.md #9. Before the fix, this crashed
    `_convert()` and fell back to leaking "Italic title" and
    "infobox video game" as bare paragraph text.
    """
    norm = WikitextMarkdownNormalizer()
    raw = """{{Italic title}}
{{infobox video game
| developer = Tour De Pizza
| publisher =
| engine = [[GameMaker]]
| released =  {{Start date and age|2023|Jan|26|paren=yes}}
| platform = [[Microsoft Windows|Windows]],
| genre = [[Platform game|Platformer]]
| image =
| modes = [[Single-player]], [[multiplayer]]
}}
'''''Pizza Tower''''' is a 2023 [[platform game]] created by the [[Indie game|indie developer]] Tour De Pizza. It was released for [[Windows]]. The game is about a pizza chef named Peppino Spaghetti. He must reach the top of a large tower to save his [[pizzeria]] from being destroyed by Pizzaface, a giant flying [[pizza]].

The gameplay consists of increasing the score, keeping combos going, finding secrets, and moving fast. Peppino has a lot of moves and attacks to do these things. At the end of each level, the player activates an escape sequence in which they must return to the beginning of the level while a timer goes down. Unlike most other platform games, the player does not have health or lives.

''Pizza Tower'' was released on January 26, 2023. It was well-liked by reviewers and players alike.<ref>{{Cite web|title=Pizza Tower|url=https://www.metacritic.com/game/pc/pizza-tower|access-date=2023-03-12|website=Metacritic|language=en}}</ref> They praised its gameplay, aesthetics, music, humor, and similarities to the [[Wario Land series|''Wario Land'' series]].<ref name="PCGamer">{{Cite web|last=McCrae|first=Scott|date=2023-01-26|title=Pizza Tower review: Madcap platforming at 100mph|url=https://www.pcgamer.com/pizza-tower-review-madcap-platforming-at-100mph/|url-status=live|archive-url=https://web.archive.org/web/20230129072724/https://www.pcgamer.com/pizza-tower-review-madcap-platforming-at-100mph/|archive-date=January 29, 2023|access-date=2023-01-29|website=[[PC Gamer]]|language=en}}</ref>

== References ==
{{reflist}}

{{Video-game-stub}}

[[Category:2023 video games]]
[[Category:Indie video games]]
[[Category:Nintendo Switch games]]
[[Category:Platform games]]
[[Category:Side-scrolling platform games]]
[[Category:Single-player video games]]
[[Category:Video games about food and drink]]
[[Category:Windows games]]"""
    doc = norm.normalize(_record(raw, title="Pizza_Tower", page_id=501))
    assert "parse_degraded" not in doc.warnings
    assert doc.warnings == ["infobox_skipped"]  # released= nests {{Start date and age}}
    assert "Italic title" not in doc.markdown
    assert "infobox video game" not in doc.markdown
    assert "Start date and age" not in doc.markdown
    assert "{{" not in doc.markdown and "}}" not in doc.markdown
    assert "# Pizza Tower" in doc.markdown
    assert "***Pizza Tower***" in doc.markdown
    assert "Pizzaface" in doc.markdown
    assert "reviewers and players alike." in doc.markdown
    assert "Category:" not in doc.markdown
    assert "<ref" not in doc.markdown


def test_normalize_real_druaga_article() -> None:
    """Real simple.wikipedia.org wikitext (fetched 2026-08-15) for the other
    article named in FINDINGS.md #9. Before the fix, this crashed and fell
    back to leaking raw pipe-joined infobox values as run-on text (e.g.
    "developer  ublArikaMatrix SoftwareSpike ChunsoftChunsoft").
    """
    norm = WikitextMarkdownNormalizer()
    raw = """{{Infobox video game
| developer = {{ubl|[[Arika]]|[[Matrix Software]]|[[Spike Chunsoft|Chunsoft]]}}
| publisher = {{vgrelease|JP|Arika|NA|[[Namco]]}}
| series = ''[[Babylonian Castle Saga]]''<br />''[[Mystery Dungeon]]''
| artist = Takeshi Okazaki
| writer = {{ubl|Ichiro Tezuka|Ichiro Mihara|Osamu Yasane}}
| platforms = [[PlayStation 2]]
| release = {{vgrelease|JP|July 29, 2004|NA|October 7, 2004}}
| genre = [[Roguelike]]
| modes = [[Single-player|1 player]]
}}

'''''The Nightmare of Druaga: Fushigi no Adventure''''' is a 2004 [[roguelike]] [[video game]] developed by [[Arika]], [[Chunsoft]], and [[Matrix Software]] and published in [[Japan]] by Arika (the [[North America]] version was published by [[Namco]]). It is sequel to ''[[The Tower of Druaga]]'' and the eight installment of ''[[Mystery Dungeon]]'' franchises.

[[Category:2004 video games]]
[[Category:PlayStation  2 games]]

{{video-game-stub}}"""
    doc = norm.normalize(_record(raw, title="The_Nightmare_of_Druaga", page_id=502))
    assert "parse_degraded" not in doc.warnings
    assert doc.warnings == ["infobox_skipped"]  # developer= nests {{ubl|...}}
    assert "vgrelease" not in doc.markdown
    assert "developer" not in doc.markdown  # the leaked-infobox-field bug from #9
    assert "{{" not in doc.markdown and "}}" not in doc.markdown
    assert "# The Nightmare of Druaga" in doc.markdown
    assert "***The Nightmare of Druaga: Fushigi no Adventure***" in doc.markdown
    assert "developed by Arika, Chunsoft, and Matrix Software" in doc.markdown
    assert "Category:" not in doc.markdown
