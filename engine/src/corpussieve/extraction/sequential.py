import bz2
import threading
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

from corpussieve.contracts.enums import JobState
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.extraction.multistream import parse_page_element
from corpussieve.jobs.state import JobStore
from corpussieve.sources.base import RawPage


def extract_sequential(
    dump_path: Path | str,
    selected_ids: set[int],
    job_store: JobStore | None = None,
    job_id: str | None = None,
    cancel_event: threading.Event | None = None,
) -> Iterator[RawPage]:
    """Single-pass streaming extraction of page_articles XML dump file."""
    d_path = Path(dump_path).resolve()
    if not d_path.exists():
        raise CorpusSieveError(
            ErrorCode.EXTRACTION_PARSE_FAILED,
            f"Sequential dump file '{d_path}' does not exist.",
        )

    if not selected_ids:
        return

    remaining_ids = set(selected_ids)
    emitted_count = 0
    last_page_id_seen = 0

    if job_store and job_id:
        chk = job_store.latest_checkpoint(job_id)
        if chk and chk.get("kind") == "sequential":
            last_page_id_seen = chk.get("last_page_id_seen", 0)
            emitted_count = chk.get("emitted_count", 0)

    try:
        f = bz2.BZ2File(d_path, mode="rb") if d_path.name.endswith(".bz2") else d_path.open("rb")
        with f:
            context = ET.iterparse(f, events=("end",))
            pages_seen = 0

            for _event, elem in context:
                if cancel_event and cancel_event.is_set():
                    if job_store and job_id:
                        job_store.transition(job_id, JobState.CANCELLED)
                    return

                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "page":
                    pages_seen += 1
                    page = parse_page_element(elem)
                    elem.clear()

                    if page:
                        if last_page_id_seen > 0 and page.page_id <= last_page_id_seen:
                            continue

                        if page.page_id in remaining_ids:
                            emitted_count += 1
                            remaining_ids.remove(page.page_id)
                            yield page

                            # Early exit if all requested IDs emitted
                            if not remaining_ids:
                                break

                    if pages_seen % 1000 == 0 and job_store and job_id:
                        job_store.save_checkpoint(
                            job_id,
                            {
                                "kind": "sequential",
                                "last_page_id_seen": page.page_id if page else last_page_id_seen,
                                "emitted_count": emitted_count,
                            },
                        )

    except CorpusSieveError:
        raise
    except Exception as e:
        raise CorpusSieveError(
            ErrorCode.EXTRACTION_PARSE_FAILED,
            f"Failed streaming sequential dump '{d_path.name}': {e}",
        ) from e
