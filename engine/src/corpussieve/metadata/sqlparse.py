import gzip
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode

_COLUMN_NAME_RE = re.compile(r"^\s*`([a-zA-Z0-9_]+)`")


def parse_create_table_columns(
    path: Path, table: str, max_bytes: int = 1024 * 64
) -> list[str] | None:
    r"""Read the leading `max_bytes` of a MediaWiki *.sql.gz dump and extract the
    ordered column names from its `CREATE TABLE \`table\` ( ... )` statement.

    MediaWiki has changed column order/composition across schema versions (e.g.
    categorylinks dropped `cl_to` in favor of `cl_target_id`). Reading column
    names from the dump's own CREATE TABLE, rather than assuming a fixed
    position, makes row parsing resilient to that drift. Returns None if no
    matching CREATE TABLE statement is found within `max_bytes`.
    """
    if not path.exists():
        raise CorpusSieveError(
            ErrorCode.METADATA_PARSE_FAILED,
            f"SQL dump file '{path}' does not exist.",
        )

    header = f"CREATE TABLE `{table}` (".lower()
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        buf = f.read(max_bytes)

    idx = buf.lower().find(header)
    if idx == -1:
        return None

    body_start = idx + len(header)
    close_idx = buf.find("\n) ENGINE", body_start)
    if close_idx == -1:
        close_idx = len(buf)
    body = buf[body_start:close_idx]

    columns: list[str] = []
    for line in body.split("\n"):
        m = _COLUMN_NAME_RE.match(line)
        if m:
            columns.append(m.group(1))
    return columns or None


def iter_insert_tuples(
    path: Path, table: str, chunk_size: int = 1024 * 1024
) -> Iterator[tuple[Any, ...]]:
    r"""Streaming character-level state machine parser for MediaWiki *.sql.gz files.

    Yields Python tuples for each row in `INSERT INTO \`table\` VALUES (...)` statements.
    Handles single-quoted strings with backslash escapes, NULL values, numbers, and binary literals.
    Does NOT load full file or full statement into memory.
    """
    target_header = f"INSERT INTO `{table}` VALUES".lower()
    target_header_alt = f"INSERT INTO {table} VALUES".lower()

    if not path.exists():
        raise CorpusSieveError(
            ErrorCode.METADATA_PARSE_FAILED,
            f"SQL dump file '{path}' does not exist.",
        )

    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            state = "SEEK_INSERT"
            tuple_items: list[Any] = []
            item_chars: list[str] = []
            in_string = False
            is_escaped = False

            buffer = ""
            buf_pos = 0

            while True:
                if buf_pos >= len(buffer):
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    buffer = chunk
                    buf_pos = 0

                ch = buffer[buf_pos]
                buf_pos += 1

                if state == "SEEK_INSERT":
                    # Look for INSERT INTO `table` VALUES
                    if ch.lower() == "i":
                        # Peek ahead to check if statement matches header
                        needed_len = max(len(target_header), len(target_header_alt))
                        lookahead = (ch + buffer[buf_pos : buf_pos + needed_len]).lower()

                        if lookahead.startswith(target_header):
                            buf_pos += len(target_header) - 1
                            state = "SEEK_TUPLE_START"
                        elif lookahead.startswith(target_header_alt):
                            buf_pos += len(target_header_alt) - 1
                            state = "SEEK_TUPLE_START"

                elif state == "SEEK_TUPLE_START":
                    if ch == "(":
                        state = "IN_TUPLE"
                        tuple_items = []
                        item_chars = []
                        in_string = False
                        is_escaped = False
                    elif ch == ";":
                        state = "SEEK_INSERT"

                elif state == "IN_TUPLE":
                    if in_string:
                        if is_escaped:
                            if ch == "n":
                                item_chars.append("\n")
                            elif ch == "r":
                                item_chars.append("\r")
                            elif ch == "t":
                                item_chars.append("\t")
                            elif ch == "0":
                                item_chars.append("\0")
                            else:
                                item_chars.append(ch)
                            is_escaped = False
                        elif ch == "\\":
                            is_escaped = True
                        elif ch == "'":
                            in_string = False
                        else:
                            item_chars.append(ch)
                    else:
                        if ch == "'":
                            in_string = True
                        elif ch == ",":
                            raw_item = "".join(item_chars).strip()
                            tuple_items.append(_parse_item(raw_item))
                            item_chars = []
                        elif ch == ")":
                            raw_item = "".join(item_chars).strip()
                            if raw_item or item_chars:
                                tuple_items.append(_parse_item(raw_item))
                            yield tuple(tuple_items)
                            tuple_items = []
                            item_chars = []
                            state = "SEEK_TUPLE_DELIMITER"
                        else:
                            item_chars.append(ch)

                elif state == "SEEK_TUPLE_DELIMITER":
                    if ch == ",":
                        state = "SEEK_TUPLE_START"
                    elif ch == ";":
                        state = "SEEK_INSERT"

    except Exception as e:
        if isinstance(e, CorpusSieveError):
            raise
        raise CorpusSieveError(
            ErrorCode.METADATA_PARSE_FAILED,
            f"Error parsing SQL dump file '{path}': {e}",
        ) from e


def _parse_item(raw: str) -> Any:
    """Parse raw unquoted token into python primitive (None, int, float, or str)."""
    if not raw:
        return ""
    if raw.upper() == "NULL":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw
