import bz2
import contextlib
import threading
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

from corpussieve.contracts.enums import JobState
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.extraction.multistream_index import group_selected
from corpussieve.jobs.state import JobStore
from corpussieve.sources.base import RawPage


def parse_page_element(page_elem: ET.Element) -> RawPage | None:
    """Parse single MediaWiki XML <page> element into RawPage model."""
    page_id: int | None = None
    namespace = 0
    title = ""
    redirect_target: str | None = None
    revision_id = 0
    wikitext = ""

    for elem in page_elem:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "id" and elem.text:
            with contextlib.suppress(ValueError):
                page_id = int(elem.text)
        elif tag == "ns" and elem.text:
            with contextlib.suppress(ValueError):
                namespace = int(elem.text)
        elif tag == "title" and elem.text:
            title = elem.text
        elif tag == "redirect":
            redirect_target = elem.attrib.get("title")
        elif tag == "revision":
            for rev_child in elem:
                rev_tag = rev_child.tag.split("}")[-1] if "}" in rev_child.tag else rev_child.tag
                if rev_tag == "id" and rev_child.text:
                    with contextlib.suppress(ValueError):
                        revision_id = int(rev_child.text)
                elif rev_tag == "text":
                    wikitext = rev_child.text or ""

    if page_id is None or not title:
        return None

    return RawPage(
        page_id=page_id,
        namespace=namespace,
        title=title,
        revision_id=revision_id,
        redirect_target=redirect_target,
        wikitext=wikitext,
    )


def extract_multistream(
    dump_path: Path | str,
    index_path: Path | str,
    selected_ids: set[int],
    job_store: JobStore | None = None,
    job_id: str | None = None,
    cancel_event: threading.Event | None = None,
) -> Iterator[RawPage]:
    """Selective extraction of page IDs using multistream bz2 index and group plans."""
    d_path = Path(dump_path).resolve()
    if not d_path.exists():
        raise CorpusSieveError(
            ErrorCode.EXTRACTION_PARSE_FAILED,
            f"Dump file '{d_path}' does not exist.",
        )

    plan = group_selected(index_path, selected_ids)
    if not plan.groups:
        return

    completed_offsets: set[int] = set()
    emitted_count = 0

    if job_store and job_id:
        chk = job_store.latest_checkpoint(job_id)
        if chk and chk.get("kind") == "multistream":
            completed_offsets = set(chk.get("completed_offsets", []))
            emitted_count = chk.get("emitted_count", 0)

    with d_path.open("rb") as f_dump:
        for group in plan.groups:
            if cancel_event and cancel_event.is_set():
                if job_store and job_id:
                    job_store.transition(job_id, JobState.CANCELLED)
                return

            if group.offset in completed_offsets:
                continue

            f_dump.seek(group.offset)
            if group.next_offset is not None:
                chunk_len = group.next_offset - group.offset
                compressed = f_dump.read(chunk_len)
            else:
                compressed = f_dump.read()

            try:
                decompressed = bz2.decompress(compressed)
            except Exception as err:
                msg = f"Corrupted bz2 stream at offset {group.offset} in '{d_path.name}': {err}"
                raise CorpusSieveError(
                    ErrorCode.EXTRACTION_PARSE_FAILED,
                    msg,
                    detail={"offset": group.offset},
                ) from err

            # Wrap in synthetic XML root
            wrapped_xml = b"<root>\n" + decompressed + b"\n</root>"
            stream_io = BytesIO(wrapped_xml)

            group_page_set = set(group.page_ids)

            try:
                context = ET.iterparse(stream_io, events=("end",))
                for _event, elem in context:
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if tag == "page":
                        page = parse_page_element(elem)
                        elem.clear()

                        if page and page.page_id in group_page_set:
                            emitted_count += 1
                            yield page

            except ET.ParseError:
                # Handle potential trailing xml boundary fragments cleanly
                pass

            completed_offsets.add(group.offset)
            if job_store and job_id:
                job_store.save_checkpoint(
                    job_id,
                    {
                        "kind": "multistream",
                        "completed_offsets": sorted(completed_offsets),
                        "emitted_count": emitted_count,
                    },
                )
