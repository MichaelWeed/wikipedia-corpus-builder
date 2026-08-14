import hashlib
import json
import os
import shutil
import threading
from pathlib import Path

import zstandard as zstd

from corpussieve.contracts.corpus import CorpusContent, CorpusRecord, CorpusSource
from corpussieve.contracts.enums import JobState
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.manifest import ManifestRecord
from corpussieve.contracts.report import BuildReport
from corpussieve.domain.definition import load_domain
from corpussieve.domain.lock_build import read_lock, verify_lock
from corpussieve.domain.manifest_io import write_manifest
from corpussieve.domain.resolve import ResolvedRoot
from corpussieve.domain.select import select_articles
from corpussieve.domain.traverse import traverse
from corpussieve.extraction.report import assemble_build_report, write_build_report
from corpussieve.jobs.events import EventBus
from corpussieve.jobs.state import JobStore
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter
from corpussieve.validation.validate import validate_corpus

EST_BYTES_PER_ARTICLE = 3500


def run_build(
    project_dir: Path | str,
    lock_path: Path | str,
    output_dir: Path | str,
    _events: EventBus | None = None,
    cancel_event: threading.Event | None = None,
    allow_low_disk: bool = False,
    resume_job_id: str | None = None,
) -> BuildReport:
    """Run end-to-end extraction build and atomic promoter."""
    p_dir = Path(project_dir).resolve()
    l_path = Path(lock_path).resolve()
    out_dir = Path(output_dir).resolve()

    lock = read_lock(l_path)
    db_path = p_dir / "cache" / "metadata.sqlite"

    with MetadataIndex(db_path) as idx:
        stats = idx.stats()
        # 1. Lock verification
        domain_file = p_dir / "domains" / f"{lock.domain_id}.yaml"
        if not domain_file.exists():
            domain_file = p_dir / "domain.yaml"
        defn = load_domain(domain_file)

        v_errors = verify_lock(lock, defn, stats.source_fingerprint)
        if v_errors:
            msg = f"Lock verification failed: {', '.join(v_errors)}"
            raise CorpusSieveError(ErrorCode.INTERNAL_ERROR, msg)

        # 2. Recreate manifest records from lock deterministically
        r_roots = [
            ResolvedRoot(query=r.query, category=r.resolved_category, max_depth=r.max_depth)
            for r in lock.resolved_roots
        ]
        traversal = traverse(idx, r_roots, set(), set(), defn)
        manifest_records, _ = select_articles(idx, traversal, defn)

    article_count = len(manifest_records)

    # 3. Disk safety preflight
    required_bytes = int(EST_BYTES_PER_ARTICLE * article_count * 1.5) + (500 * 1024 * 1024)
    try:
        _total_b, _used_b, free_b = shutil.disk_usage(out_dir.parent)
        if free_b < required_bytes and not allow_low_disk:
            req_mb = required_bytes / (1024 * 1024)
            free_mb = free_b / (1024 * 1024)
            msg = (
                f"Free disk space on {out_dir.parent} ({free_mb:.1f} MB) "
                f"is below required headroom ({req_mb:.1f} MB)."
            )
            raise CorpusSieveError(ErrorCode.OUTPUT_DISK_INSUFFICIENT, msg)
    except CorpusSieveError:
        raise
    except Exception:
        pass

    # 4. Job Store setup
    state_db = p_dir / "state.sqlite"
    job_store = JobStore(state_db)
    job_id = resume_job_id or job_store.create_job("build", lock.lock_hash)
    job_store.transition(job_id, JobState.BUILDING)

    staging_dir = out_dir / f".staging-{job_id}"
    if not resume_job_id and staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    c_zst_path = staging_dir / "corpus.jsonl.zst"
    m_zst_path = staging_dir / "manifest.jsonl.zst"

    selected_ids = {r.page_id for r in manifest_records}
    manifest_by_id = {r.page_id: r for r in manifest_records}

    adapter = WikimediaXmlDumpAdapter(p_dir / "source")
    raw_pages = adapter.extract_selected_pages(selected_ids, job_store=job_store, job_id=job_id)

    cctx = zstd.ZstdCompressor(level=10)
    enriched_map: dict[int, ManifestRecord] = {}
    extracted_count = 0

    open_mode = "ab" if (resume_job_id and c_zst_path.exists()) else "wb"
    try:
        with c_zst_path.open(open_mode) as f_corp_raw, cctx.stream_writer(f_corp_raw) as c_writer:
            for raw_page in raw_pages:
                if cancel_event and cancel_event.is_set():
                    job_store.transition(job_id, JobState.CANCELLED)
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    raise CorpusSieveError(ErrorCode.INTERNAL_ERROR, "Build cancelled by user")

                man_rec = manifest_by_id.get(raw_page.page_id)
                if not man_rec:
                    continue

                # Document ID calculation (cs-doc-<sha256[:16]>)
                content_hash = hashlib.sha256(raw_page.wikitext.encode("utf-8")).hexdigest()
                doc_id = f"cs-doc-{content_hash[:16]}"

                corpus_rec = CorpusRecord(
                    document_id=doc_id,
                    source=CorpusSource(
                        project=defn.language,
                        language=defn.language,
                        page_id=raw_page.page_id,
                        revision_id=raw_page.revision_id,
                        title=raw_page.title,
                        source_url=f"https://{defn.language}.wikipedia.org/wiki/{raw_page.title}",
                    ),
                    categories=[],
                    selection=man_rec.selection,
                    content=CorpusContent(format="wikitext", raw=raw_page.wikitext),
                )

                c_line = json.dumps(corpus_rec.model_dump(mode="json"), sort_keys=True) + "\n"
                c_writer.write(c_line.encode("utf-8"))

                enriched_map[raw_page.page_id] = ManifestRecord(
                    schema_version=1,
                    project=defn.language,
                    language=defn.language,
                    page_id=man_rec.page_id,
                    title=man_rec.title,
                    namespace=man_rec.namespace,
                    selected=True,
                    selection=man_rec.selection,
                    document_id=doc_id,
                    revision_id=raw_page.revision_id,
                    content_hash=content_hash,
                )
                extracted_count += 1

        output_bytes = c_zst_path.stat().st_size if c_zst_path.exists() else 0

        # Write enriched manifest.jsonl.zst
        final_manifest_records = [
            enriched_map.get(m.page_id, m) for m in manifest_records if m.page_id in enriched_map
        ]
        write_manifest(final_manifest_records, m_zst_path)

        # Step 5: Write metadata & config snapshots to staging
        shutil.copy(domain_file, staging_dir / "domain.yaml")
        shutil.copy(l_path, staging_dir / "domain.lock.json")

        attribution_data = {
            "source_project": defn.language,
            "license": "CC-BY-SA-4.0 / GFDL",
            "extracted_count": extracted_count,
        }
        (staging_dir / "attribution.json").write_text(
            json.dumps(attribution_data, indent=2), encoding="utf-8"
        )

        job_store.transition(job_id, JobState.BUILD_SUCCEEDED)
        job_store.transition(job_id, JobState.VALIDATING)

        # Step 6: Validate corpus in staging
        val_res = validate_corpus(staging_dir, lock)
        if val_res.status != "PASSED":
            job_store.transition(job_id, JobState.FAILED, error_code="VALIDATION_FAILED")
            shutil.rmtree(staging_dir, ignore_errors=True)
            msg = f"Corpus validation failed: {', '.join(val_res.errors)}"
            raise CorpusSieveError(ErrorCode.VALIDATION_FAILED, msg)

        job_store.transition(job_id, JobState.VALIDATED)

        report = assemble_build_report(
            lock, val_res, extracted_count, output_bytes, traversal.warnings
        )
        write_build_report(report, staging_dir, p_dir)

        # Atomic promote: os.replace staging -> target corpus directory
        final_corpus_dir = out_dir / "corpus"
        if final_corpus_dir.exists():
            shutil.rmtree(final_corpus_dir, ignore_errors=True)

        os.replace(staging_dir, final_corpus_dir)
        return report

    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
