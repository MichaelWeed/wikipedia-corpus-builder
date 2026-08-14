import re
import unicodedata

WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def slugify(title: str) -> str:
    """Path-traversal safe filename slugify algorithm."""
    # 1. NFC normalization
    norm = unicodedata.normalize("NFC", title)

    # 2. Replace non-alphanumeric/dot/underscore/dash with hyphen
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", norm)

    # 3. Collapse multiple hyphens & strip leading/trailing dots and dashes
    collapsed = re.sub(r"-+", "-", cleaned).strip(".-")

    if not collapsed:
        collapsed = "untitled"

    # 4. Truncate to max 80 chars
    truncated = collapsed[:80].rstrip(".-")

    # 5. Check Windows reserved names
    upper_base = truncated.upper()
    if upper_base in WINDOWS_RESERVED:
        truncated = f"{truncated}_"

    return truncated
