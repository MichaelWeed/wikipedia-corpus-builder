import re
from dataclasses import dataclass

RECOGNIZED_KINDS = (
    "pages-articles-multistream-index.txt.bz2",
    "pages-articles-multistream.xml.bz2",
    "pages-articles.xml.bz2",
    "categorylinks.sql.gz",
    "page.sql.gz",
)

PATTERN = re.compile(
    r"^([a-z0-9_]+)-(\d{8})-(pages-articles-multistream-index\.txt\.bz2|pages-articles-multistream\.xml\.bz2|pages-articles\.xml\.bz2|categorylinks\.sql\.gz|page\.sql\.gz)$"
)


@dataclass(frozen=True)
class DumpNameParts:
    project: str
    language: str
    date: str
    kind: str


def parse_dump_filename(name: str) -> DumpNameParts | None:
    """Parse Wikimedia dump filename into component parts.

    Returns None for unrecognized filenames.
    """
    match = PATTERN.match(name)
    if not match:
        return None

    proj, date, kind = match.groups()

    lang = proj[:-4] if proj.endswith("wiki") and len(proj) > 4 else proj

    return DumpNameParts(project=proj, language=lang, date=date, kind=kind)
