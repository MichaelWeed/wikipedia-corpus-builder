import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from corpussieve import __version__
from corpussieve.contracts.domain import DomainDefinition, DomainFacets, DomainPolicy, DomainRoot
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.protocol import JsonRpcError, JsonRpcErrorDetail, JsonRpcResponse
from corpussieve.contracts.providers import ProviderEndpoint
from corpussieve.domain.definition import load_domain, save_domain
from corpussieve.domain.lock_build import compile_lock, read_lock, write_lock
from corpussieve.domain.manifest_io import write_manifest
from corpussieve.domain.preview import build_preview, explain_page
from corpussieve.domain.select import select_articles
from corpussieve.exporters.jsonl import export_jsonl
from corpussieve.exporters.markdown import export_markdown
from corpussieve.extraction.build import run_build
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
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


def _send_response(resp: JsonRpcResponse) -> None:
    line = json.dumps(resp.model_dump(mode="json"), sort_keys=True)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _send_notification(method: str, params: dict[str, Any]) -> None:
    noti = {"jsonrpc": "2.0", "method": method, "params": params}
    line = json.dumps(noti, sort_keys=True)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


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
            facets=DomainFacets(include=include_facets),
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
                from corpussieve.jobs.state import JobStore

                store = JobStore(state_db)
                act = store.active_job("build")
                store.close()
                if act:
                    resume_job_id = str(act.get("job_id"))

        report = run_build(
            project_dir=p_dir,
            lock_path=lock_path,
            output_dir=output_dir,
            allow_low_disk=allow_low_disk,
            resume_job_id=resume_job_id,
        )
        return report.model_dump(mode="json")

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
