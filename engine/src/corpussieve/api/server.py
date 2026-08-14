import contextlib
import json
import re
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from corpussieve import __version__
from corpussieve.contracts.domain import DomainDefinition, DomainFacets, DomainPolicy, DomainRoot
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.intent import BoundaryQuestion, FacetProposal
from corpussieve.contracts.protocol import JsonRpcError, JsonRpcErrorDetail, JsonRpcResponse
from corpussieve.contracts.providers import ProviderEndpoint
from corpussieve.domain.definition import load_domain, save_domain
from corpussieve.domain.intent import (
    apply_answers,
    propose_boundary_questions,
    propose_facets,
)
from corpussieve.domain.lock_build import compile_lock, read_lock, write_lock
from corpussieve.domain.manifest_io import write_manifest
from corpussieve.domain.preview import build_preview, explain_page
from corpussieve.domain.select import select_articles
from corpussieve.exporters.jsonl import export_jsonl
from corpussieve.exporters.markdown import export_markdown
from corpussieve.extraction.build import run_build
from corpussieve.jobs.events import EventBus
from corpussieve.jobs.registry import get_build_registry
from corpussieve.jobs.state import JobStore
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.models.base import ModelProvider
from corpussieve.models.capability import run_capability_test
from corpussieve.models.config import (
    load_configured_endpoints,
    save_configured_endpoints,
)
from corpussieve.models.registry import detect_all, provider_for
from corpussieve.safety.preconditions import check_purge_preconditions
from corpussieve.safety.purge import execute_purge
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter
from corpussieve.validation.validate import validate_corpus


def _resolve_provider_and_model(params: dict[str, Any]) -> tuple[ModelProvider, str]:
    endpoint_url = params.get("endpoint") or params.get("base_url")
    prov_req = params.get("provider")
    model_id = str(params.get("model") or params.get("model_id") or "default")

    endpoints = load_configured_endpoints() or detect_all()
    target_ep = None

    if endpoint_url:
        target_ep = next((e for e in endpoints if e.base_url == endpoint_url), None)
        if not target_ep:
            prov_kind: Literal["ollama", "lmstudio"] = (
                "ollama" if (prov_req == "ollama" or "11434" in str(endpoint_url)) else "lmstudio"
            )
            target_ep = ProviderEndpoint(
                provider=prov_kind,
                base_url=str(endpoint_url),
                is_loopback="127.0.0.1" in str(endpoint_url) or "localhost" in str(endpoint_url),
            )
    elif prov_req:
        target_ep = next((e for e in endpoints if e.provider == prov_req), None)

    if not target_ep and endpoints:
        target_ep = endpoints[0]

    if not target_ep:
        prov_kind = "ollama" if (prov_req == "ollama" or not prov_req) else "lmstudio"
        base = endpoint_url or (
            "http://127.0.0.1:11434" if prov_kind == "ollama" else "http://127.0.0.1:1234"
        )
        target_ep = ProviderEndpoint(
            provider=prov_kind,
            base_url=str(base),
            is_loopback="127.0.0.1" in str(base) or "localhost" in str(base),
        )

    p = provider_for(target_ep)
    return p, model_id


def _send_response(resp: JsonRpcResponse) -> None:
    line = json.dumps(resp.model_dump(mode="json"), sort_keys=True)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _send_notification(method: str, params: dict[str, Any]) -> None:
    noti = {"jsonrpc": "2.0", "method": method, "params": params}
    line = json.dumps(noti, sort_keys=True)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


# How long build.start will wait for the background thread to assign a
# job_id before giving up. This only covers lock verification, traversal,
# and disk preflight (near-instant in practice) — the extraction itself
# runs after this point and is tracked separately via build.status polling.
BUILD_START_TIMEOUT_S = 60.0


def _start_build_background(
    p_dir: Path,
    lock_path: Path,
    output_dir: Path,
    allow_low_disk: bool,
    resume_job_id: str | None,
) -> dict[str, Any]:
    """Run a build on a background thread so the stdin-dispatch loop stays
    free to serve build.status/build.cancel while extraction is in flight.

    Blocks only until run_build() has assigned a job_id (fast — lock
    verification/traversal/disk preflight, not the extraction loop itself).
    A failure in that fast setup phase is raised here, same as the old
    fully-synchronous build.start; a failure during extraction is instead
    recorded on the registry for build.status to report.
    """
    registry = get_build_registry()
    cancel_event = threading.Event()
    events_bus = EventBus()
    job_id_box: dict[str, str] = {}
    start_error_box: dict[str, Exception] = {}
    started = threading.Event()

    def _on_job_started(job_id: str) -> None:
        job_id_box["job_id"] = job_id
        registry.register(job_id, cancel_event)
        started.set()

    events_bus.subscribe(lambda evt: registry.update_progress(job_id_box.get("job_id", ""), evt))

    def _run() -> None:
        try:
            report = run_build(
                project_dir=p_dir,
                lock_path=lock_path,
                output_dir=output_dir,
                events=events_bus,
                cancel_event=cancel_event,
                allow_low_disk=allow_low_disk,
                resume_job_id=resume_job_id,
                on_job_started=_on_job_started,
            )
            job_id = job_id_box.get("job_id")
            if job_id:
                registry.finish(job_id, report=report.model_dump(mode="json"))
        except Exception as exc:
            job_id = job_id_box.get("job_id")
            if job_id:
                registry.finish(job_id, error=str(exc), cancelled=cancel_event.is_set())
            else:
                # Failed before a job_id was ever assigned — surface it as a
                # build.start error instead of making the caller wait out
                # the full started.wait() timeout below.
                start_error_box["exc"] = exc
                started.set()

    threading.Thread(target=_run, daemon=True, name="corpussieve-build").start()

    if not started.wait(timeout=BUILD_START_TIMEOUT_S):
        raise CorpusSieveError(
            ErrorCode.INTERNAL_ERROR,
            f"Build did not start within {BUILD_START_TIMEOUT_S:.0f}s "
            "(lock verification/traversal may be taking unusually long).",
        )

    if "exc" in start_error_box:
        exc = start_error_box["exc"]
        if isinstance(exc, CorpusSieveError):
            raise exc
        raise CorpusSieveError(ErrorCode.INTERNAL_ERROR, f"Build failed to start: {exc}") from exc

    return {"job_id": job_id_box["job_id"], "status": "started"}


def _build_status(job_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Return current status for job_id.

    Reads live from the in-process registry if this server process started
    the build; otherwise falls back to the persisted JobStore row (e.g. the
    desktop app was restarted mid-build — the background thread is gone,
    but the job's last known state and interrupted flag are still on disk).
    """
    entry = get_build_registry().get(job_id)
    if entry:
        with entry.lock:
            return {
                "job_id": job_id,
                "status": entry.status,
                "progress": (
                    entry.latest_progress.model_dump(mode="json") if entry.latest_progress else None
                ),
                "error": entry.error,
                "report": entry.report,
            }

    p_dir = Path(params.get("project_dir", "")).resolve()
    state_db = p_dir / "state.sqlite"
    if state_db.exists():
        store = JobStore(state_db)
        row = store.get_job(job_id)
        store.close()
        if row:
            return {
                "job_id": job_id,
                "status": str(row["state"]),
                "progress": None,
                "error": row.get("error_message"),
                "report": None,
                "interrupted": bool(row["interrupted"]),
            }

    raise CorpusSieveError(ErrorCode.INTERNAL_ERROR, f"Unknown build job '{job_id}'")


def dispatch_method(method: str, params: dict[str, Any]) -> Any:  # noqa: C901
    """Dispatch JSON-RPC method call to service layer."""
    if method == "engine.hello":
        return {
            "protocol_version": 1,
            "engine_version": __version__,
        }

    elif method == "source.inspect":
        source_path = params.get("source", "")
        adapter = WikimediaXmlDumpAdapter(source_path)
        return adapter.inspect().model_dump(mode="json")

    elif method == "metadata.build":
        source_path = params.get("source", "")
        p_dir = Path(params.get("project_dir", "")).resolve()
        p_dir.mkdir(parents=True, exist_ok=True)
        adapter = WikimediaXmlDumpAdapter(source_path)
        db_path = p_dir / "cache" / "metadata.sqlite"
        build_metadata_index(adapter, db_path)

        # Record where the source dump actually lives. The desktop wizard
        # lets a user point at a dump anywhere on disk (it isn't copied into
        # project_dir/source), so run_build() needs this to find it later --
        # without it, build.start fails with "Source path .../source does
        # not exist" for every project whose source isn't already sitting
        # at that exact default path.
        import yaml  # type: ignore[import-untyped]

        proj_file_path = p_dir / "project.yaml"
        proj_data: dict[str, Any] = {}
        if proj_file_path.exists():
            with contextlib.suppress(Exception):
                loaded = yaml.safe_load(proj_file_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    proj_data = loaded
        proj_data["source_paths"] = [str(Path(source_path).resolve())]
        proj_file_path.write_text(yaml.safe_dump(proj_data, sort_keys=False), encoding="utf-8")

        return {"status": "success", "db_path": str(db_path)}

    elif method == "metadata.search":
        p_dir = Path(params.get("project_dir", "")).resolve()
        query = params.get("query", "")
        limit = params.get("limit", 50)
        db_path = p_dir / "cache" / "metadata.sqlite"
        with MetadataIndex(db_path) as idx:
            res_hits = idx.search_categories(query, limit=limit)
            return [asdict(r) for r in res_hits]

    elif method == "model.detect":
        endpoints = detect_all()
        results: list[dict[str, Any]] = []
        for ep in endpoints:
            try:
                p = provider_for(ep)
                models = p.list_models()
                results.append(
                    {
                        "provider": ep.provider,
                        "base_url": ep.base_url,
                        "is_loopback": ep.is_loopback,
                        "reachable": True,
                        "model_count": len(models),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "provider": ep.provider,
                        "base_url": ep.base_url,
                        "is_loopback": ep.is_loopback,
                        "reachable": False,
                        "error": str(e),
                    }
                )
        return results

    elif method == "model.add":
        url = str(params.get("url") or params.get("base_url") or "")
        prov_arg = params.get("provider")
        is_loop = "127.0.0.1" in url or "localhost" in url
        prov_type = prov_arg or ("ollama" if "11434" in url else "lmstudio")
        ep = ProviderEndpoint(
            provider="ollama" if prov_type == "ollama" else "lmstudio",
            base_url=url,
            is_loopback=is_loop,
        )
        existing = load_configured_endpoints()
        filtered = [e for e in existing if e.base_url != url]
        filtered.append(ep)
        save_configured_endpoints(filtered)
        return {
            "status": "added",
            "provider": ep.provider,
            "base_url": ep.base_url,
            "is_loopback": ep.is_loopback,
        }

    elif method == "model.list":
        endpoints = load_configured_endpoints()
        if not endpoints:
            endpoints = detect_all()
        all_models: list[dict[str, Any]] = []
        for ep in endpoints:
            try:
                p = provider_for(ep)
                models = p.list_models()
                for mod_info in models:
                    all_models.append(
                        {
                            "provider": ep.provider,
                            "base_url": ep.base_url,
                            "model_id": mod_info.model_id,
                            "loaded": mod_info.loaded,
                            "model_type": mod_info.model_type,
                            "capability": mod_info.capability_result,
                        }
                    )
            except Exception as e:
                all_models.append(
                    {
                        "provider": ep.provider,
                        "base_url": ep.base_url,
                        "error": str(e),
                    }
                )
        return all_models

    elif method == "model.test":
        model_id = str(params.get("model") or params.get("model_id") or "")
        endpoint_url = params.get("endpoint") or params.get("base_url")
        prov_req = params.get("provider")
        endpoints = load_configured_endpoints() or detect_all()
        target_ep = None
        if endpoint_url:
            target_ep = next((e for e in endpoints if e.base_url == endpoint_url), None)
            if not target_ep:
                prov_name = prov_req or ("ollama" if "11434" in str(endpoint_url) else "lmstudio")
                target_ep = ProviderEndpoint(
                    provider="ollama" if prov_name == "ollama" else "lmstudio",
                    base_url=str(endpoint_url),
                    is_loopback="127.0.0.1" in str(endpoint_url)
                    or "localhost" in str(endpoint_url),
                )
        if not target_ep and endpoints:
            target_ep = endpoints[0]
        if not target_ep:
            prov_kind: Literal["ollama", "lmstudio"] = (
                "ollama" if prov_req == "ollama" else "lmstudio"
            )
            base = endpoint_url or (
                "http://127.0.0.1:11434" if prov_kind == "ollama" else "http://127.0.0.1:1234"
            )
            target_ep = ProviderEndpoint(
                provider=prov_kind,
                base_url=str(base),
                is_loopback="127.0.0.1" in str(base) or "localhost" in str(base),
            )
        p = provider_for(target_ep)
        cap = run_capability_test(p, model_id)
        return cap.model_dump(mode="json")

    elif method == "domain.proposeFacets":
        intent = str(params.get("intent", ""))
        language = str(params.get("language") or "en")
        p, model_id = _resolve_provider_and_model(params)
        proposal = propose_facets(p, model_id, intent, language=language)
        return proposal.model_dump(mode="json")

    elif method == "domain.boundaryQuestions":
        intent = str(params.get("intent", ""))
        facets_raw = params.get("facets")
        if isinstance(facets_raw, dict):
            facet_prop = FacetProposal.model_validate(facets_raw)
        else:
            facet_prop = FacetProposal(include_facets=[], exclude_facets=[], rationale="")
        p, model_id = _resolve_provider_and_model(params)
        questions = propose_boundary_questions(p, model_id, intent, facet_prop)
        return [q.model_dump(mode="json") for q in questions]

    elif method == "domain.applyAnswers":
        domain_file = Path(params.get("domain") or params.get("domain_path") or "").resolve()
        p_dir = Path(params.get("project_dir", "")).resolve()
        if not domain_file.exists() and (p_dir / "domain.yaml").exists():
            domain_file = p_dir / "domain.yaml"
        defn = load_domain(domain_file)
        raw_questions = params.get("questions") or []
        questions = [BoundaryQuestion.model_validate(q) for q in raw_questions]
        answers = params.get("answers") or {}
        updated_defn = apply_answers(defn, questions, answers)
        save_domain(updated_defn, domain_file)
        return updated_defn.model_dump(mode="json")

    elif method == "domain.compile":
        domain_file = Path(params.get("domain", "")).resolve()
        p_dir = Path(params.get("project_dir", "")).resolve()
        defn = load_domain(domain_file)
        db_path = p_dir / "cache" / "metadata.sqlite"
        with MetadataIndex(db_path) as idx:
            stats = idx.stats()
            lock, _traversal = compile_lock(defn, idx, stats.source_fingerprint)
            # Same dual-write locations as `corpussieve domain compile` (CLI):
            # next to the YAML, and project_dir/domain.lock.json for the
            # standard project layout that domain.explain/domain.audit expect.
            lock_path = domain_file.with_name(f"{domain_file.stem}.lock.json")
            write_lock(lock, lock_path)
            write_lock(lock, p_dir / "domain.lock.json")
            return lock.model_dump(mode="json")

    elif method == "domain.create":
        # Desktop-only convenience method: writes project_dir/domain.yaml
        # directly from the wizard's draft state (name, language, intent,
        # multiple root categories, a shared max_depth). This is a superset
        # of the CLI's `domain create` (which writes a single-root template
        # to project_dir/domains/<id>.yaml); the desktop always targets the
        # standard project_dir/domain.yaml path that domain.compile/preview/
        # explain already read and write.
        p_dir = Path(params.get("project_dir", "")).resolve()
        p_dir.mkdir(parents=True, exist_ok=True)
        name = str(params.get("name") or "My Domain")
        language = str(params.get("language") or "en")
        intent = str(params.get("intent") or "")
        raw_roots = params.get("roots") or [name]
        max_depth = int(params.get("max_depth", 6))
        include_facets = [str(f) for f in (params.get("facets") or [])]
        exclude_facets = [str(f) for f in (params.get("exclude_facets") or [])]

        slug = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-")
        slug = re.sub(r"-+", "-", slug) or "domain"
        if len(slug) < 2:
            slug = f"{slug}-domain"
        slug = slug[:63]

        roots: list[DomainRoot] = []
        for raw in raw_roots:
            query = str(raw).strip()
            if not query:
                continue
            if not query.lower().startswith("category:"):
                query = f"Category:{query}"
            roots.append(DomainRoot(query=query, max_depth=max_depth))
        if not roots:
            roots = [DomainRoot(query=f"Category:{name}", max_depth=max_depth)]

        defn = DomainDefinition(
            id=slug,
            name=name,
            description=intent or f"Domain definition for {name}",
            language=language,
            policy=DomainPolicy(),
            facets=DomainFacets(include=include_facets, exclude=exclude_facets),
            roots=roots,
        )
        domain_path = p_dir / "domain.yaml"
        save_domain(defn, domain_path)
        return {"status": "created", "domain_id": defn.id, "domain_path": str(domain_path)}

    elif method == "domain.preview":
        domain_file = Path(params.get("domain", "")).resolve()
        p_dir = Path(params.get("project_dir", "")).resolve()
        defn = load_domain(domain_file)
        db_path = p_dir / "cache" / "metadata.sqlite"
        with MetadataIndex(db_path) as idx:
            stats = idx.stats()
            lock, traversal = compile_lock(defn, idx, stats.source_fingerprint)
            records, _ = select_articles(idx, traversal, defn)
            manifest_path = p_dir / "cache" / "manifest.preview.jsonl.zst"
            write_manifest(records, manifest_path)
            preview = build_preview(idx, lock, traversal, records, defn)
        return preview.model_dump(mode="json")

    elif method == "domain.explain":
        domain_file = Path(params.get("domain", "")).resolve()
        p_dir = Path(params.get("project_dir", "")).resolve()
        page_title = params.get("page_title", "")
        defn = load_domain(domain_file)
        db_path = p_dir / "cache" / "metadata.sqlite"
        lock_path = domain_file.with_name(f"{domain_file.stem}.lock.json")
        if not lock_path.exists():
            lock_path = p_dir / "domain.lock.json"
        lock = read_lock(lock_path)
        with MetadataIndex(db_path) as idx:
            stats = idx.stats()
            traversal = compile_lock(defn, idx, stats.source_fingerprint)[1]
            records, _ = select_articles(idx, traversal, defn)
            page_target: str | int = int(page_title) if page_title.isdigit() else page_title
            explain = explain_page(idx, lock, records, page_target, defn)
        return explain.model_dump(mode="json")

    elif method == "build.start":
        p_dir = Path(params.get("project_dir", "")).resolve()
        lock_path = Path(params.get("domain", "")).resolve()
        output_dir = Path(params.get("output", "")).resolve()
        allow_low_disk = bool(params.get("allow_low_disk", False))
        resume = bool(params.get("resume", False))
        resume_job_id = None
        if resume:
            state_db = p_dir / "state.sqlite"
            if state_db.exists():
                store = JobStore(state_db)
                act = store.active_job("build")
                store.close()
                if act:
                    resume_job_id = str(act.get("job_id"))

        return _start_build_background(p_dir, lock_path, output_dir, allow_low_disk, resume_job_id)

    elif method == "build.status":
        job_id = str(params.get("job_id") or "")
        return _build_status(job_id, params)

    elif method == "build.cancel":
        job_id = str(params.get("job_id") or "")
        if not get_build_registry().request_cancel(job_id):
            raise CorpusSieveError(
                ErrorCode.INTERNAL_ERROR, f"No active build job '{job_id}' to cancel"
            )
        return {"job_id": job_id, "status": "cancel_requested"}

    elif method == "corpus.validate":
        corpus_path = Path(params.get("corpus", "")).resolve()
        lock_file = corpus_path / "domain.lock.json"
        if not lock_file.exists():
            lock_file = corpus_path.parent / "domain.lock.json"
        lock = read_lock(lock_file)
        val_res = validate_corpus(corpus_path, lock)
        return val_res.model_dump(mode="json")

    elif method == "export.markdown":
        corpus_path = Path(params.get("corpus", "")).resolve()
        output_path = Path(params.get("output", "")).resolve()
        return export_markdown(corpus_dir=corpus_path, output_dir=output_path)

    elif method == "export.jsonl":
        corpus_path = Path(params.get("corpus", "")).resolve()
        output_path = Path(params.get("output", "")).resolve()
        norm = bool(params.get("normalized", False))
        return export_jsonl(corpus_dir=corpus_path, output_dir=output_path, normalized=norm)

    elif method == "purge.plan":
        p_dir = Path(params.get("project_dir", "")).resolve()
        plan, blockers = check_purge_preconditions(p_dir)
        if blockers or not plan:
            return {
                "purge_eligible": False,
                "blockers": [b.model_dump(mode="json") for b in blockers],
            }
        return {
            "purge_eligible": True,
            "plan": plan.model_dump(mode="json"),
            "blockers": [],
        }

    elif method == "purge.confirm":
        p_dir = Path(params.get("project_dir", "")).resolve()
        mode_val = params.get("mode", "trash")
        token = params.get("confirm_token", "")
        plan, blockers = check_purge_preconditions(p_dir)
        if blockers or not plan:
            msgs = ", ".join(b.message for b in blockers)
            raise CorpusSieveError(ErrorCode.PURGE_OUTPUT_UNVERIFIED, f"Purge blocked: {msgs}")
        p_mode: Literal["trash", "permanent"] = "permanent" if mode_val == "permanent" else "trash"
        res_purge = execute_purge(plan, mode=p_mode, confirm_token=token)
        return res_purge.model_dump(mode="json")

    else:
        raise CorpusSieveError(
            ErrorCode.INTERNAL_ERROR,
            f"Unknown RPC method '{method}'",
        )


def serve_stdio() -> None:
    """Read NDJSON RPC requests from stdin and write JSON-RPC responses to stdout."""
    for line in sys.stdin:
        line_str = line.strip()
        if not line_str:
            continue

        req_id = None
        try:
            req_data = json.loads(line_str)
            req_id = req_data.get("id")
            method = req_data.get("method", "")
            params = req_data.get("params", {})

            result = dispatch_method(method, params)
            _send_response(JsonRpcResponse(jsonrpc="2.0", id=req_id, result=result))

        except CorpusSieveError as cse:
            err_obj = JsonRpcError(
                code=-32603,
                message=cse.message,
                data=JsonRpcErrorDetail(
                    code=cse.code,
                    message=cse.message,
                    detail=cse.detail,
                ),
            )
            _send_response(JsonRpcResponse(jsonrpc="2.0", id=req_id, error=err_obj))
        except Exception as e:
            err_obj = JsonRpcError(
                code=-32603,
                message=str(e),
                data=JsonRpcErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=str(e),
                    detail={},
                ),
            )
            _send_response(JsonRpcResponse(jsonrpc="2.0", id=req_id, error=err_obj))
