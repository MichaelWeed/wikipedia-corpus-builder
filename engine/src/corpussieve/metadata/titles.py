def normalize_title(title: str) -> str:
    """Normalize MediaWiki page/category title.

    - Strips surrounding whitespace.
    - Replaces spaces with underscores.
    - Uppercases first character per MediaWiki default case semantics.
    """
    s = title.strip().replace(" ", "_")
    if not s:
        return ""
    return s[0].upper() + s[1:]
