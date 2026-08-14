import bz2
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).resolve().parent / "fixwiki"


def generate_fixtures() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    # 60 synthetic pages definition
    # Format: (page_id, title, ns, is_redirect, text, categories)
    pages_data: list[tuple[int, str, int, int, str, list[tuple[str, str]]]] = []

    # 1. Main category & video games pages
    pages_data.append(
        (
            1,
            "Super_Mario_Bros",
            0,
            0,
            "Super Mario Bros platform game. [[Category:Video games]] [[Category:Platform games]]",
            [("Video_games", "page"), ("Platform_games", "page")],
        )
    )
    pages_data.append(
        (
            2,
            "The_Legend_of_Zelda",
            0,
            0,
            "Zelda action game. [[Category:Video games]] [[Category:Action-adventure games]]",
            [("Video_games", "page"), ("Action-adventure_games", "page")],
        )
    )
    pages_data.append(
        (
            3,
            "Super_Mario_Bros_Redirect",
            0,
            1,
            "#REDIRECT [[Super_Mario_Bros]]",
            [],
        )
    )
    pages_data.append(
        (
            4,
            "Multi_Root_Game",
            0,
            0,
            "Multi Root Game. [[Category:Action games]] [[Category:Adventure games]]",
            [("Action_games", "page"), ("Adventure_games", "page")],
        )
    )
    pages_data.append(
        (
            5,
            "Pokémon_(fixture)",
            0,
            0,
            "Pokémon game franchise. [[Category:Video games]] [[Category:Nintendo games]]",
            [("Video_games", "page"), ("Nintendo_games", "page")],
        )
    )
    pages_data.append(
        (
            6,
            "日本のゲーム",
            0,
            0,
            "Japanese video games overview. [[Category:Video games]]",
            [("Video_games", "page")],
        )
    )
    pages_data.append(
        (
            7,
            "Malformed_Wikitext_Page",
            0,
            0,
            "Malformed wikitext [[Unclosed link and {{unclosed template [[Category:Video games]]",
            [("Video_games", "page")],
        )
    )

    # Category pages (ns 14) & hierarchy
    categories_info = [
        ("Video_games", [("Games", "subcat")]),
        ("Platform_games", [("Video_games", "subcat")]),
        ("Action-adventure_games", [("Video_games", "subcat")]),
        ("Action_games", [("Video_games", "subcat")]),
        ("Adventure_games", [("Video_games", "subcat")]),
        ("Nintendo_games", [("Video_games", "subcat")]),
        ("Board_games", [("Games", "subcat"), ("Tabletop_games", "subcat")]),
        ("Tabletop_games", [("Games", "subcat")]),
        # Cycle A -> B -> C -> A
        ("Cycle_A", [("Cycle_C", "subcat")]),
        ("Cycle_B", [("Cycle_A", "subcat")]),
        ("Cycle_C", [("Cycle_B", "subcat")]),
        ("Explode_Root", [("Video_games", "subcat")]),
    ]

    page_id_counter = 8
    for cat_name, parent_cats in categories_info:
        cat_title = f"Category:{cat_name}"
        cat_links = [(parent, "subcat") for parent, _ in parent_cats]
        pages_data.append(
            (
                page_id_counter,
                cat_title,
                14,
                0,
                f"Category page for {cat_name}.",
                cat_links,
            )
        )
        page_id_counter += 1

    # Cycle member page
    pages_data.append(
        (
            page_id_counter,
            "Cycle_Page_1",
            0,
            0,
            "Page inside cycle A. [[Category:Cycle_A]]",
            [("Cycle_A", "page")],
        )
    )
    page_id_counter += 1

    # Excluded Board games page
    pages_data.append(
        (
            page_id_counter,
            "Monopoly",
            0,
            0,
            "Monopoly is a board game. [[Category:Board_games]]",
            [("Board_games", "page")],
        )
    )
    page_id_counter += 1

    # Non-zero namespaces
    pages_data.append(
        (
            page_id_counter,
            "Talk:Super_Mario_Bros",
            1,
            0,
            "Discussion about Super Mario Bros.",
            [],
        )
    )
    page_id_counter += 1
    pages_data.append(
        (
            page_id_counter,
            "Template:Game_Infobox",
            10,
            0,
            "Infobox template for games.",
            [],
        )
    )
    page_id_counter += 1

    # Runaway explosion categories & pages (30 subcategories + pages)
    for i in range(1, 31):
        subcat_name = f"Explode_Sub_{i}"
        pages_data.append(
            (
                page_id_counter,
                f"Category:{subcat_name}",
                14,
                0,
                f"Explosion category {i}",
                [("Explode_Root", "subcat")],
            )
        )
        page_id_counter += 1

        pages_data.append(
            (
                page_id_counter,
                f"Exploded_Article_{i}",
                0,
                0,
                f"Article {i} in exploded category.",
                [(subcat_name, "page")],
            )
        )
        page_id_counter += 1

    # Sort pages by page_id for determinism
    pages_data.sort(key=lambda x: x[0])

    # 1. Build XML streams (multistream: 8 pages per stream)
    xml_header = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.mediawiki.org/xml/export-0.11/ '
        'http://www.mediawiki.org/xml/export-0.11.xsd" version="0.11" xml:lang="en">\n'
        "  <siteinfo>\n"
        "    <sitename>fixwiki</sitename>\n"
        "    <dbname>fixwiki</dbname>\n"
        "    <base>https://fixwiki.example/wiki/Main_Page</base>\n"
        "    <generator>CorpusSieve Synthetic Generator</generator>\n"
        "    <case>first-letter</case>\n"
        "    <namespaces>\n"
        '      <namespace key="-2" case="first-letter">Media</namespace>\n'
        '      <namespace key="-1" case="first-letter">Special</namespace>\n'
        '      <namespace key="0" case="first-letter" />\n'
        '      <namespace key="1" case="first-letter">Talk</namespace>\n'
        '      <namespace key="10" case="first-letter">Template</namespace>\n'
        '      <namespace key="14" case="first-letter">Category</namespace>\n'
        "    </namespaces>\n"
        "  </siteinfo>\n"
    )
    xml_footer = "</mediawiki>\n"

    def page_to_xml(p_id: int, title: str, ns: int, text: str, rev_id: int = 100) -> str:
        sha1 = hashlib.sha1(text.encode("utf-8")).hexdigest()
        bytes_len = len(text.encode("utf-8"))
        return (
            "  <page>\n"
            f"    <title>{title}</title>\n"
            f"    <ns>{ns}</ns>\n"
            f"    <id>{p_id}</id>\n"
            "    <revision>\n"
            f"      <id>{rev_id + p_id}</id>\n"
            "      <timestamp>2026-08-01T00:00:00Z</timestamp>\n"
            "      <contributor>\n"
            "        <username>FixtureBot</username>\n"
            "        <id>1</id>\n"
            "      </contributor>\n"
            "      <comment>Fixture page</comment>\n"
            "      <model>wikitext</model>\n"
            "      <format>text/x-wiki</format>\n"
            f'      <text bytes="{bytes_len}" xml:space="preserve">{text}</text>\n'
            f"      <sha1>{sha1}</sha1>\n"
            "    </revision>\n"
            "  </page>\n"
        )

    # Build single stream XML
    single_xml_parts = [xml_header]
    for p_id, title, ns, _is_red, text, _cats in pages_data:
        single_xml_parts.append(page_to_xml(p_id, title, ns, text))
    single_xml_parts.append(xml_footer)
    full_xml_bytes = "".join(single_xml_parts).encode("utf-8")

    single_bz2_path = FIXTURE_DIR / "fixwiki-20260801-pages-articles.xml.bz2"
    single_bz2_path.write_bytes(bz2.compress(full_xml_bytes))

    # Build multistream XML & index
    multistream_bz2_path = FIXTURE_DIR / "fixwiki-20260801-pages-articles-multistream.xml.bz2"
    index_path = FIXTURE_DIR / "fixwiki-20260801-pages-articles-multistream-index.txt.bz2"

    multistream_file_bytes = bytearray()
    index_lines: list[str] = []

    # Stream 0: Header only
    header_bz2 = bz2.compress(xml_header.encode("utf-8"))
    stream_offset = 0
    multistream_file_bytes.extend(header_bz2)
    stream_offset += len(header_bz2)

    # Group pages into streams of max 8 pages
    chunk_size = 8
    for i in range(0, len(pages_data), chunk_size):
        chunk = pages_data[i : i + chunk_size]
        chunk_xml = "".join(
            page_to_xml(p_id, title, ns, text) for p_id, title, ns, _is_red, text, _cats in chunk
        )
        chunk_bz2 = bz2.compress(chunk_xml.encode("utf-8"))

        for p_id, title, _ns, _is_red, _text, _cats in chunk:
            index_lines.append(f"{stream_offset}:{p_id}:{title}\n")

        multistream_file_bytes.extend(chunk_bz2)
        stream_offset += len(chunk_bz2)

    # Footer stream
    footer_bz2 = bz2.compress(xml_footer.encode("utf-8"))
    multistream_file_bytes.extend(footer_bz2)

    multistream_bz2_path.write_bytes(bytes(multistream_file_bytes))
    index_text = "".join(index_lines).encode("utf-8")
    index_path.write_bytes(bz2.compress(index_text))

    # 2. Build SQL Dumps: page.sql.gz & categorylinks.sql.gz
    page_sql_header = (
        "DROP TABLE IF EXISTS `page`;\n"
        "CREATE TABLE `page` (\n"
        "  `page_id` int(10) unsigned NOT NULL AUTO_INCREMENT,\n"
        "  `page_namespace` int(11) NOT NULL DEFAULT '0',\n"
        "  `page_title` varbinary(255) NOT NULL DEFAULT '',\n"
        "  `page_restrictions` tinyblob NOT NULL,\n"
        "  `page_is_redirect` tinyint(3) unsigned NOT NULL DEFAULT '0',\n"
        "  `page_is_new` tinyint(3) unsigned NOT NULL DEFAULT '0',\n"
        "  `page_random` double unsigned NOT NULL DEFAULT '0',\n"
        "  `page_touched` varbinary(14) NOT NULL DEFAULT '',\n"
        "  `page_links_updated` varbinary(14) DEFAULT NULL,\n"
        "  `page_latest` int(10) unsigned NOT NULL DEFAULT '0',\n"
        "  `page_len` int(10) unsigned NOT NULL DEFAULT '0',\n"
        "  `page_content_model` varbinary(32) DEFAULT NULL,\n"
        "  `page_lang` varbinary(35) DEFAULT NULL,\n"
        "  PRIMARY KEY (`page_id`)\n"
        ") ENGINE=InnoDB DEFAULT CHARSET=binary;\n"
        "INSERT INTO `page` VALUES "
    )

    page_sql_values: list[str] = []
    for p_id, title, ns, is_red, text, _cats in pages_data:
        escaped_title = title.replace("'", "\\'")
        txt_len = len(text.encode("utf-8"))
        page_sql_values.append(
            f"({p_id},{ns},'{escaped_title}',b'',{is_red},0,0.5,"
            f"'20260801000000',NULL,{100 + p_id},{txt_len},'wikitext','en')"
        )

    page_sql_body = page_sql_header + ",\n".join(page_sql_values) + ";\n"
    page_sql_path = FIXTURE_DIR / "fixwiki-20260801-page.sql.gz"
    page_sql_path.write_bytes(gzip.compress(page_sql_body.encode("utf-8")))

    cl_sql_header = (
        "DROP TABLE IF EXISTS `categorylinks`;\n"
        "CREATE TABLE `categorylinks` (\n"
        "  `cl_from` int(10) unsigned NOT NULL DEFAULT '0',\n"
        "  `cl_to` varbinary(255) NOT NULL DEFAULT '',\n"
        "  `cl_sortkey` varbinary(230) NOT NULL DEFAULT '',\n"
        "  `cl_timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,\n"
        "  `cl_sortkey_prefix` varbinary(255) NOT NULL DEFAULT '',\n"
        "  `cl_collation` varbinary(32) NOT NULL DEFAULT '',\n"
        "  `cl_type` enum('page','subcat','file') NOT NULL DEFAULT 'page',\n"
        "  PRIMARY KEY (`cl_from`,`cl_to`)\n"
        ") ENGINE=InnoDB DEFAULT CHARSET=binary;\n"
        "INSERT INTO `categorylinks` VALUES "
    )

    cl_sql_values: list[str] = []
    for p_id, _title, _ns, _is_red, _text, cats in pages_data:
        for cl_to, cl_type in cats:
            escaped_cl_to = cl_to.replace("'", "\\'")
            cl_sql_values.append(
                f"({p_id},'{escaped_cl_to}','','2026-08-01 00:00:00','','uppercase','{cl_type}')"
            )

    cl_sql_body = cl_sql_header + ",\n".join(cl_sql_values) + ";\n"
    cl_sql_path = FIXTURE_DIR / "fixwiki-20260801-categorylinks.sql.gz"
    cl_sql_path.write_bytes(gzip.compress(cl_sql_body.encode("utf-8")))

    # 3. Write expected.json ground truth
    expected_data: dict[str, Any] = {
        "video_games_domain": {
            "selected_pages": [
                "Super_Mario_Bros",
                "The_Legend_of_Zelda",
                "Pokémon_(fixture)",
                "日本のゲーム",
                "Malformed_Wikitext_Page",
            ],
            "excluded_pages": [
                "Monopoly",
                "Cycle_Page_1",
            ],
            "counts_by_depth": {
                "0": 1,  # Category:Video_games
                "1": 5,  # Pages/Subcats at depth 1
            },
        }
    }

    expected_path = FIXTURE_DIR / "expected.json"
    expected_path.write_text(
        json.dumps(expected_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("Synthetic fixwiki golden fixtures generated successfully.")


if __name__ == "__main__":
    generate_fixtures()
