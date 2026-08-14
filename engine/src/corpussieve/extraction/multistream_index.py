import bz2
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode


@dataclass(frozen=True)
class IndexEntry:
    offset: int
    page_id: int
    title: str


@dataclass(frozen=True)
class StreamGroup:
    offset: int
    next_offset: int | None
    page_ids: list[int]


@dataclass(frozen=True)
class StreamPlan:
    groups: list[StreamGroup]
    missing_ids: list[int]


def iter_index(path: Path | str) -> Iterator[IndexEntry]:
    """Stream and parse bz2 or text multistream index file (offset:page_id:title)."""
    p = Path(path).resolve()
    if not p.exists():
        raise CorpusSieveError(
            ErrorCode.EXTRACTION_PARSE_FAILED,
            f"Multistream index file '{p}' does not exist.",
        )

    try:
        if p.name.endswith(".bz2"):
            f = bz2.open(p, "rt", encoding="utf-8", errors="replace")  # noqa: SIM115
        else:
            f = p.open("r", encoding="utf-8", errors="replace")
        with f:
            for line_no, line in enumerate(f, start=1):
                s_line = line.rstrip("\r\n")
                if not s_line:
                    continue
                parts = s_line.split(":", 2)
                if len(parts) < 3:
                    raise CorpusSieveError(
                        ErrorCode.EXTRACTION_PARSE_FAILED,
                        f"Malformed index line {line_no} in '{p.name}': {line}",
                        detail={"line_no": line_no, "line": line},
                    )
                try:
                    offset = int(parts[0])
                    page_id = int(parts[1])
                    title = parts[2]
                except ValueError as err:
                    raise CorpusSieveError(
                        ErrorCode.EXTRACTION_PARSE_FAILED,
                        f"Invalid numbers on index line {line_no} in '{p.name}': {err}",
                        detail={"line_no": line_no, "line": line},
                    ) from err

                yield IndexEntry(offset=offset, page_id=page_id, title=title)

    except CorpusSieveError:
        raise
    except Exception as e:
        raise CorpusSieveError(
            ErrorCode.EXTRACTION_PARSE_FAILED,
            f"Failed reading multistream index '{p}': {e}",
        ) from e


def group_selected(index_path: Path | str, selected_ids: set[int]) -> StreamPlan:
    """Group selected page IDs into byte stream offset ranges based on multistream index."""
    if not selected_ids:
        return StreamPlan(groups=[], missing_ids=[])

    all_offsets: list[int] = []
    offset_page_map: dict[int, list[int]] = defaultdict(list)
    found_ids: set[int] = set()

    for entry in iter_index(index_path):
        if not all_offsets or all_offsets[-1] != entry.offset:
            all_offsets.append(entry.offset)
        if entry.page_id in selected_ids:
            offset_page_map[entry.offset].append(entry.page_id)
            found_ids.add(entry.page_id)

    missing_ids = sorted(selected_ids - found_ids)

    # Filter to active offsets and compute next_offset
    selected_offsets = sorted(offset_page_map.keys())
    groups: list[StreamGroup] = []

    for _i, off in enumerate(selected_offsets):
        # find next distinct offset in all_offsets
        idx_in_all = all_offsets.index(off)
        next_off = all_offsets[idx_in_all + 1] if idx_in_all + 1 < len(all_offsets) else None
        groups.append(
            StreamGroup(
                offset=off,
                next_offset=next_off,
                page_ids=sorted(offset_page_map[off]),
            )
        )

    return StreamPlan(groups=groups, missing_ids=missing_ids)
