import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from corpussieve import __version__
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.protocol import JsonRpcError, JsonRpcErrorDetail, JsonRpcResponse
from corpussieve.domain.definition import load_domain
from corpussieve.domain.lock_build import compile_lock, read_lock, write_lock
from corpussieve.exporters.jsonl import export_jsonl
from corpussieve.exporters.markdown import export_markdown
from corpussieve.extraction.build import run_build
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
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

    elif method == "domain.compile":
        domain_file = Path(params.get("domain", "")).resolve()
        p_dir = Path(params.get("project_dir", "")).resolve()
        defn = load_domain(domain_file)
        db_path = p_dir / "cache" / "metadata.sqlite"
        with MetadataIndex(db_path) as idx:
            stats = idx.stats()
            lock, _traversal = compile_lock(defn, idx, stats.source_fingerprint)
            lock_path = p_dir / "domains" / f"{lock.domain_id}.lock.json"
            write_lock(lock, lock_path)
            return lock.model_dump(mode="json")

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
