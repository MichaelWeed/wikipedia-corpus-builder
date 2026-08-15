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


def test_normalize_real_rock_paper_shotgun_article() -> None:
    """Real simple.wikipedia.org wikitext (fetched 2026-08-15 from the
    canonical corpus of a real simplewiki build, page_id 1095673) --
    surfaced by running the full v0.1 CLI pipeline end-to-end after fixing
    the two real articles from the original FINDINGS.md #9 report.

    Distinct root cause from the rest of #9: an infobox param left as a
    single bare `''` (`| caption = ''`), combined with *any* bold/italic
    run later in the same article (however far away -- here, the article's
    own opening `'''''Rock Paper Shotgun'''''`), makes mwparserfromhell's
    apostrophe-run resolution misjudge where the unclosed `''` actually
    closes and fail to recognize `{{Infobox website ...}}` as a template at
    all -- not a crash, just silently no Template node, so the entire
    infobox (including nested templates and wikilinks inside it) passes
    through completely raw with braces, pipes, and field names intact.
    `RECURSE_OTHERS` (the earlier #9 fix) can't help here: there's no
    Template node to find in the first place.
    """
    norm = WikitextMarkdownNormalizer()
    raw = """{{Italic title}}
{{Use dmy dates}}
{{Infobox website
| name = ''Rock Paper Shotgun''
| logo =
| screenshot =
| screenshot_size =
| caption = ''
| company_type = [[Subsidiary]]
| location = [[Brighton]]
| country = England
| key_people =
| industry = [[Video game industry]]
| url = {{URL|https://rockpapershotgun.com/}}
| website_type = [[Video game journalism]]
| registration = Optional
| launched = {{start date and age|df=yes|2007|07|13}}
| current_status = Active
| owner = [[Gamer Network]]
| founder = {{ubl|[[Kieron Gillen]]|[[Jim Rossignol]]|Alec Meer|John Walker}}
| editor = Katharine Castle
}}

'''''Rock Paper Shotgun'''''{{efn|Also '''''Rock, Paper, Shotgun'''''}} is a British [[video game]] news website. It was launched in July 2007 to focus on [[PC game]]s. It was acquired by the [[Gamer Network]],  led by ''[[Eurogamer]]'', in May 2017.<ref>{{cite web|url=http://www.gamesindustry.biz/articles/2017-05-03-gamer-network-acquires-rock-paper-shotgun |title=Gamer Network acquires Rock, Paper, Shotgun |first=Dan |last=Pearson |date=3 May 2017 |access-date=3 May 2017 |work=[[GamesIndustry.biz]] |url-status=live |archive-url=https://web.archive.org/web/20170503141138/http://www.gamesindustry.biz/articles/2017-05-03-gamer-network-acquires-rock-paper-shotgun |archive-date=3 May 2017 }}</ref><ref>{{cite web |url=https://www.rockpapershotgun.com/2007/07/13/the-website-that-saved-the-world/ |title=The Website That Saved The World |author=RPS |date=13 July 2007 |website=Rock Paper Shotgun |access-date=30 June 2019 |archive-date=30 June 2019 |archive-url=https://web.archive.org/web/20190630124602/https://www.rockpapershotgun.com/2007/07/13/the-website-that-saved-the-world/ |url-status=live }}</ref>

==References==
{{Notelist}}
{{Reflist}}

[[Category:Video game websites]]"""
    doc = norm.normalize(_record(raw, title="Rock_Paper_Shotgun", page_id=503))
    assert "parse_degraded" not in doc.warnings
    assert doc.warnings == ["infobox_skipped"]  # url= nests {{URL|...}}
    assert "{{" not in doc.markdown and "}}" not in doc.markdown
    assert "Infobox website" not in doc.markdown
    assert "| name" not in doc.markdown
    assert "# Rock Paper Shotgun" in doc.markdown
    assert "***Rock Paper Shotgun***" in doc.markdown
    assert "British" in doc.markdown and "video game news website" in doc.markdown
    assert "Category:" not in doc.markdown


def test_normalize_real_gallery_in_div_does_not_leak_raw() -> None:
    """Real (trimmed) simple.wikipedia.org wikitext, from the article
    "History of video game consoles (fourth generation)" -- found running
    the full v0.1 CLI pipeline end-to-end against all 3,372 real simplewiki
    articles.

    A <gallery> wrapped in a <div>, combined with unrelated bold/italic
    markup appearing *later* in the same article (here, the "Popular
    games" bulleted list), was enough for mwparserfromhell to fail to
    recognize the <gallery>...</gallery> block as a Tag node at all -- not
    a crash, just silent, so it (and a <ref> plus a template nested inside
    it) passed through as raw literal text. `RECURSE_OTHERS` alone doesn't
    help here since there's no Tag node in the first place; this needs the
    defensive regex fallback that runs after the AST-based tag removal.
    Real content trimmed to the two sections that reproduce it (full
    article is ~16 KB; this needs the div/gallery block *and* something
    with bold/italic markup after it, however far away).
    """
    norm = WikitextMarkdownNormalizer()
    raw = """===Other===
<div style="display:table; margin:0 auto;">
<gallery>
File:Gamate.jpg|[[Gamate]] <br>Released in 1991<ref>[http://www.videogamegazette.com/gamate/gamate.html Gamate Archive] {{Webarchive|url=https://web.archive.org/web/20110511073905/http://www.videogamegazette.com/gamate/gamate.html |date=2011-05-11 }}, Video Game Gazette. Retrieved 2010-06-14.</ref>
File:Supervision.jpg|[[Watara Supervision]] <br>Released in 1992
</gallery>
</div>

== Popular games ==
* [[Sonic the Hedgehog (16-bit)|Sonic the Hedgehog]]
"""
    doc = norm.normalize(_record(raw, title="History_of_video_game_consoles", page_id=506))
    assert "parse_degraded" not in doc.warnings
    assert "raw_tag_fallback_stripped" in doc.warnings
    assert "{{" not in doc.markdown and "}}" not in doc.markdown
    assert "<ref" not in doc.markdown and "<gallery" not in doc.markdown
    assert "Webarchive" not in doc.markdown
    assert "Gamate.jpg" not in doc.markdown
    assert "## Popular games" in doc.markdown
    assert "Sonic the Hedgehog" in doc.markdown


def test_normalize_real_totk_article_nested_wikilink_in_file_caption() -> None:
    """Real simple.wikipedia.org wikitext (fetched from a real simplewiki
    build's canonical corpus, page_id 1000197). Found running the full
    v0.1 CLI pipeline end-to-end against all 3,372 real articles after
    fixing the two originally-reported FINDINGS.md #9 articles plus the
    Rock Paper Shotgun and gallery-in-div cases -- a fourth, distinct
    manifestation of the same underlying bug class.

    `[[File:...|thumb|caption with [[Nintendo Switch]] inside]]` is
    everyday real-article syntax -- image captions routinely contain
    wikilinks. `filter_wikilinks()` without `RECURSE_OTHERS` found both the
    outer File: link and the nested one; removing the outer one (File:
    links are dropped entirely) orphaned the nested one, and calling
    `wikicode.replace()` on it next in the same loop raised the same
    ValueError class as the template/tag cases, hitting the same silent
    whole-article fallback.
    """
    norm = WikitextMarkdownNormalizer()
    raw = """{{Italic title}}
{{Infobox video game
| title = The Legend of Zelda: {{nowrap|Tears of the Kingdom}}
| image = The Legend of Zelda Tears of the Kingdom.svg
| caption = Game logo
| developer = [[Nintendo EPD]]{{efn|Additional work by [[Monolith Soft]]}}
| publisher = [[Nintendo]]
| series = ''[[The Legend of Zelda]]''
| platforms = [[Nintendo Switch]]
| released = May 12, 2023
| genre = [[Action-adventure]]
| modes = [[Single-player]]
| director = [[Hidemaro Fujibayashi]]
| producer = [[Eiji Aonuma]]
| artist = Satoru Takizawa
| composer = {{ubl|Manaka Kataoka|Maasa Miyoshi|Masato Ohashi|Tsukasa Usui}}
| designer = {{ubl|Mari Shirakawa|Naoki Mori|Akihito Toda}}
| programmer = Takahiro Okuda
| engine = ModuleSystem
}}
'''''The Legend of Zelda: Tears of the Kingdom''''' is a 2023 [[Action adventure game|action-adventure]] game developed and published by [[Nintendo]] for the [[Nintendo Switch]]. The sequel to ''[[The Legend of Zelda: Breath of the Wild]]'' (2017), ''Tears of the Kingdom'' keeps aspects including the open world of Hyrule, which has been expanded to allow for more vertical exploration. The player controls [[Link (The Legend of Zelda)|Link]] as he searches for [[Princess Zelda]] and fights to stop the [[Ganon|Demon King]] from destroying the world.

[[File:Nintendo Switch – OLED-Modell (The Legend of Zelda - Tears of the Kingdom) 20230510 HOF02399 RAW-Export.png|thumb|[[Nintendo Switch]] ([[OLED]] model) special edition for the game]]

Upon release, the game received critical acclaim for its improvements, expanded open world, and features encouraging exploration and explosions.<ref name="MC">{{Cite web|title=''The Legend of Zelda: Tears of the Kingdom'' for Switch Reviews|url=https://www.metacritic.com/game/switch/the-legend-of-zelda-tears-of-the-kingdom|url-status=live|archive-url=https://web.archive.org/web/20230511230606/https://www.metacritic.com/game/switch/the-legend-of-zelda-tears-of-the-kingdom|archive-date=May 11, 2023|access-date=June 1, 2023|website=[[Metacritic]]}}</ref> It sold more than 10 million copies in its first three days of release and over 18.51 million copies by June 2023, making it one of the best-selling games on the Nintendo Switch.{{cn}}

==References==
{{Reflist}}

===Notes===
{{notelist}}

{{The Legend of Zelda series}}

{{Video-game-stub}}

[[Category:2023 video games]]
[[Category:The Legend of Zelda games]]
[[Category:Nintendo Switch games]]"""
    doc = norm.normalize(
        _record(raw, title="The_Legend_of_Zelda:_Tears_of_the_Kingdom", page_id=504)
    )
    assert "parse_degraded" not in doc.warnings
    assert "{{" not in doc.markdown and "}}" not in doc.markdown
    assert "<ref" not in doc.markdown
    assert "Cite web" not in doc.markdown
    assert "# The Legend of Zelda: Tears of the Kingdom" in doc.markdown
    assert "***The Legend of Zelda: Tears of the Kingdom***" in doc.markdown
    assert "sequel to *The Legend of Zelda: Breath of the Wild*" in doc.markdown
    assert "Category:" not in doc.markdown
    # The File: link (including its nested [[Nintendo Switch]]/[[OLED]]
    # wikilinks) is dropped entirely per design -- confirms the nested
    # links didn't just leak raw once the crash stopped, they're gone.
    assert "OLED-Modell" not in doc.markdown


def test_normalize_real_fire_emblem_article_bare_references_tag() -> None:
    """Real simple.wikipedia.org wikitext (fetched from a real simplewiki
    build's canonical corpus, page_id 1192043) -- found in the same full
    3,372-article pipeline run as the TOTK case above.

    `<references />` (self-closing -- renders the citation list a <ref>
    elsewhere feeds into) is a distinct tag from `<ref>` itself, not in the
    tag-removal set. Usually sits under a "References" heading the
    line-based section-drop already removes, but this article has it
    floating with no such heading, so it survived into the output with
    nothing left to render (all `<ref>` tags elsewhere had already been
    removed).
    """
    norm = WikitextMarkdownNormalizer()
    raw = """{{Other uses||Remake works released in 2008|Fire Emblem New Dark Dragon and Sword of Light|}}
<references />


'''Fire Emblem: Shadow Dragon and the Blade of Light''' (Fire Emblem: Shadow Dragon and the Blade of Light ) is a simulation role-playing game for [[Nintendo Entertainment System|the Family Computer]] released by [[Nintendo]] on April 20, 1990.This is the first game in [[Fire Emblem|the Fire Emblem]] series.

In this article, "Dark Dragon and the Sword of Light" and "New Dark Dragon and the Sword of Light" will be abbreviated to "Dark Dragon" and "New Dark Dragon" respectively as necessary.

{{video-game-stub}}

[[Category:1990 video games]]"""
    doc = norm.normalize(
        _record(raw, title="Fire_Emblem:_Shadow_Dragon_and_the_Blade_of_Light", page_id=505)
    )
    assert "parse_degraded" not in doc.warnings
    assert "<references" not in doc.markdown
    assert "# Fire Emblem: Shadow Dragon and the Blade of Light" in doc.markdown
    assert "**Fire Emblem: Shadow Dragon and the Blade of Light**" in doc.markdown
    assert "simulation role-playing game" in doc.markdown
    assert "Category:" not in doc.markdown
