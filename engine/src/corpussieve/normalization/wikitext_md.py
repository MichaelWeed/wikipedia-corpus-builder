import re
from typing import Any

import mwparserfromhell

from corpussieve.contracts.corpus import CorpusRecord
from corpussieve.normalization.base import NormalizedDoc


class WikitextMarkdownNormalizer:
    """Converts MediaWiki wikitext into RAG-ready Markdown."""

    def normalize(self, record: CorpusRecord) -> NormalizedDoc:
        title = record.source.title.replace("_", " ")
        raw_text = record.content.raw
        warnings: list[str] = []

        frontmatter: dict[str, Any] = {
            "title": title,
            "project": record.source.project,
            "language": record.source.language,
            "page_id": record.source.page_id,
            "revision_id": record.source.revision_id,
            "license": "CC BY-SA 4.0",
        }
        if record.document_id:
            frontmatter["document_id"] = record.document_id

        try:
            markdown, norm_warnings = self._convert(title, raw_text)
            warnings.extend(norm_warnings)
        except Exception:
            warnings.append("parse_degraded")
            # Safe degradation fallback: strip wikitext special chars
            clean_text = re.sub(r"[\[\]{}|\'#=]", "", raw_text)
            lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
            markdown = f"# {title}\n\n" + "\n\n".join(lines)

        return NormalizedDoc(
            title=title,
            frontmatter=frontmatter,
            markdown=markdown,
            warnings=warnings,
        )

    def _convert(self, title: str, wikitext: str) -> tuple[str, list[str]]:
        warnings: list[str] = []

        # 1. Remove references sections & sections below them
        drop_sections = {"references", "external links", "see also", "further reading", "notes"}
        lines = wikitext.splitlines()
        filtered_lines: list[str] = []
        dropping = False
        for line in lines:
            h_match = re.match(r"^\s*={2,6}\s*(.*?)\s*={2,6}\s*$", line)
            if h_match:
                sec_name = h_match.group(1).strip().lower()
                dropping = sec_name in drop_sections
            if not dropping:
                filtered_lines.append(line)

        text_stripped = "\n".join(filtered_lines)

        # 2. Parse AST with mwparserfromhell
        wikicode = mwparserfromhell.parse(text_stripped)

        # Strip HTML comments & magic words
        for comment in wikicode.filter_comments():
            wikicode.remove(comment)

        text = str(wikicode)
        text = re.sub(r"__([A-Z_]+)__", "", text)
        wikicode = mwparserfromhell.parse(text)

        # Handle tags (<ref>, <gallery>, etc.). RECURSE_OTHERS yields only
        # tags not nested inside another tag already in this pass, so
        # removing an outer one (e.g. <ref><gallery>...) can't orphan an
        # inner one still queued for removal -- mwparserfromhell's
        # `remove()` raises ValueError on a node no longer in the tree,
        # which a plain recursive filter_tags() can hand you.
        for tag in wikicode.filter_tags(wikicode.RECURSE_OTHERS):
            tag_name = str(tag.tag).strip().lower()
            if tag_name in {"ref", "gallery", "style", "script"}:
                wikicode.remove(tag)

        # Handle templates & infoboxes. Same RECURSE_OTHERS reasoning as
        # above -- real infoboxes routinely nest templates in param values
        # (e.g. `{{Infobox video game|released={{Start date and age|...}}}}`),
        # and a plain recursive filter_templates() yields both the infobox
        # and that nested template as separate nodes. Removing/replacing the
        # infobox first (it's found first, being outermost) detaches the
        # nested template from the tree; reaching it next in the same loop
        # and calling remove() on it then raises ValueError, which the
        # caller's broad `except Exception` was silently swallowing --
        # discarding the *entire* article to a crude character-stripped
        # fallback instead of just this one infobox. See qa/FINDINGS.md #9.
        for tpl in wikicode.filter_templates(wikicode.RECURSE_OTHERS):
            tpl_name = str(tpl.name).strip()
            if tpl_name.lower().startswith("infobox"):
                # Convert Infobox to **Facts** bullet list if scalar plain text
                facts: list[str] = []
                is_scalar = True
                for param in tpl.params:
                    name = str(param.name).strip()
                    val = str(param.value).strip()
                    if not val or "\n" in val or "{" in val or "[" in val:
                        is_scalar = False
                        break
                    facts.append(f"- **{name}**: {val}")

                if is_scalar and facts:
                    fact_block = "**Facts**\n" + "\n".join(facts)
                    wikicode.replace(tpl, fact_block)
                else:
                    warnings.append("infobox_skipped")
                    wikicode.remove(tpl)
            else:
                wikicode.remove(tpl)

        # Handle tables (<table ...> or {| ... |}). RECURSE_OTHERS again --
        # HTML tables can legitimately nest.
        for tag in wikicode.filter_tags(wikicode.RECURSE_OTHERS):
            if str(tag.tag).strip().lower() == "table":
                warnings.append("table_skipped")
                wikicode.remove(tag)

        # Handle {| ... |} wikitext table blocks
        text_tables = re.findall(r"\{\|[\s\S]*?\|\}", str(wikicode))
        if text_tables:
            warnings.append("table_skipped")
            for t_str in text_tables:
                wikicode.replace(t_str, "")

        # Handle Wikilinks
        for link in wikicode.filter_wikilinks():
            target = str(link.title).strip()
            if target.lower().startswith(("category:", "file:", "image:", ":category:", ":file:")):
                wikicode.remove(link)
            else:
                label = str(link.text).strip() if link.text else target
                wikicode.replace(link, label)

        # Handle External Links
        for ext_link in wikicode.filter_external_links():
            label = str(ext_link.title).strip() if ext_link.title else str(ext_link.url).strip()
            wikicode.replace(ext_link, label)

        # Convert headings to Markdown ##
        res_text = str(wikicode)
        res_lines: list[str] = []
        for line in res_text.splitlines():
            h_match = re.match(r"^\s*(={2,6})\s*(.*?)\s*={2,6}\s*$", line)
            if h_match:
                level = len(h_match.group(1))
                h_title = h_match.group(2).strip()
                hashes = "#" * max(2, level)
                res_lines.append(f"{hashes} {h_title}")
            else:
                # Formatting quotes: '''bold''' -> **bold**, ''italic'' -> *italic*
                formatted = line
                formatted = re.sub(r"\'\'\'(.*?)\'\'\'", r"**\1**", formatted)
                formatted = re.sub(r"\'\'(.*?)\'\'", r"*\1*", formatted)
                res_lines.append(formatted)

        # Build output with H1 title
        body = "\n".join(res_lines).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        markdown = f"# {title}\n\n{body}" if body else f"# {title}"
        return markdown, warnings
