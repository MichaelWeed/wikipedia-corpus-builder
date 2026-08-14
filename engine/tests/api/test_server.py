import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"
EXAMPLE_DOMAIN = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "examples"
    / "domains"
    / "video-games.yaml"
)


def test_engine_serve_subprocess_handshake_and_inspect() -> None:
    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"

    proc = subprocess.Popen(
        [sys.executable, "-m", "corpussieve.cli.main", "engine", "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    assert proc.stdin is not None
    assert proc.stdout is not None

    # 1. Send engine.hello
    req1 = {"jsonrpc": "2.0", "id": 1, "method": "engine.hello", "params": {}}
    proc.stdin.write(json.dumps(req1) + "\n")
    proc.stdin.flush()

    line1 = proc.stdout.readline()
    if not line1:
        stderr_text = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"Engine serve exited cleanly or crashed. Stderr:\n{stderr_text}")
    resp1 = json.loads(line1)
    assert resp1["id"] == 1
    assert resp1["result"]["protocol_version"] == 1

    # 2. Send source.inspect
    req2 = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "source.inspect",
        "params": {"source": str(FIXWIKI_DIR)},
    }
    proc.stdin.write(json.dumps(req2) + "\n")
    proc.stdin.flush()

    line2 = proc.stdout.readline()
    resp2 = json.loads(line2)
    assert resp2["id"] == 2
    assert resp2["result"]["adapter"] == "wikimedia_xml_dump"

    proc.stdin.close()
    proc.wait(timeout=5)


def test_engine_serve_subprocess_preview_and_explain(tmp_path: Path) -> None:
    """domain.preview and domain.explain are listed in the desktop client's
    protocol methods and called by PreviewScreen -- verify the server actually
    implements them (it previously did not; calls would hit 'Unknown RPC
    method')."""
    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"

    proj_dir = tmp_path / "proj"
    domain_path = proj_dir / "domain.yaml"
    proj_dir.mkdir(parents=True)
    shutil.copy(EXAMPLE_DOMAIN, domain_path)

    proc = subprocess.Popen(
        [sys.executable, "-m", "corpussieve.cli.main", "engine", "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    def call(req_id: int, method: str, params: dict) -> dict:
        req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        proc.stdin.write(json.dumps(req) + "\n")  # type: ignore[union-attr]
        proc.stdin.flush()  # type: ignore[union-attr]
        line = proc.stdout.readline()  # type: ignore[union-attr]
        if not line:
            stderr_text = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Engine serve exited/crashed. Stderr:\n{stderr_text}")
        resp = json.loads(line)
        assert "error" not in resp or resp["error"] is None, resp.get("error")
        return resp["result"]

    call(1, "engine.hello", {})
    call(2, "metadata.build", {"source": str(FIXWIKI_DIR), "project_dir": str(proj_dir)})
    compile_res = call(
        3, "domain.compile", {"domain": str(domain_path), "project_dir": str(proj_dir)}
    )
    assert len(compile_res["lock_hash"]) > 0

    preview_res = call(
        4, "domain.preview", {"domain": str(domain_path), "project_dir": str(proj_dir)}
    )
    assert preview_res["article_count"] > 0
    assert preview_res["estimated_output_bytes"] > 0

    explain_res = call(
        5,
        "domain.explain",
        {
            "domain": str(domain_path),
            "project_dir": str(proj_dir),
            "page_title": "Super_Mario_Bros",
        },
    )
    assert explain_res["status"] == "included"

    proc.stdin.close()
    proc.wait(timeout=5)


def test_engine_serve_subprocess_create_compile_preview_flow(tmp_path: Path) -> None:
    """The exact sequence apps/desktop/src/wizard/DomainScreen.tsx now runs:
    domain.create (writes project_dir/domain.yaml from wizard draft state,
    not a pre-existing file) -> domain.compile -> domain.preview. Previously
    nothing in the desktop wizard ever created domain.yaml, so compile would
    always fail with 'file does not exist'."""
    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"

    proj_dir = tmp_path / "proj"
    proj_dir.mkdir(parents=True)

    proc = subprocess.Popen(
        [sys.executable, "-m", "corpussieve.cli.main", "engine", "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    def call(req_id: int, method: str, params: dict) -> dict:
        req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        proc.stdin.write(json.dumps(req) + "\n")  # type: ignore[union-attr]
        proc.stdin.flush()  # type: ignore[union-attr]
        line = proc.stdout.readline()  # type: ignore[union-attr]
        if not line:
            stderr_text = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Engine serve exited/crashed. Stderr:\n{stderr_text}")
        resp = json.loads(line)
        assert "error" not in resp or resp["error"] is None, resp.get("error")
        return resp["result"]

    call(1, "engine.hello", {})
    call(2, "metadata.build", {"source": str(FIXWIKI_DIR), "project_dir": str(proj_dir)})

    create_res = call(
        3,
        "domain.create",
        {
            "project_dir": str(proj_dir),
            "name": "My Video Games Corpus",
            "language": "en",
            "intent": "Keep things related to video games",
            "roots": ["Video_games"],  # no "Category:" prefix, as the desktop UI collects it
            "max_depth": 6,
            "facets": [],
        },
    )
    assert create_res["status"] == "created"
    domain_path = create_res["domain_path"]
    assert domain_path == str(proj_dir / "domain.yaml")
    assert Path(domain_path).exists()

    compile_res = call(4, "domain.compile", {"domain": domain_path, "project_dir": str(proj_dir)})
    assert len(compile_res["lock_hash"]) > 0

    preview_res = call(5, "domain.preview", {"domain": domain_path, "project_dir": str(proj_dir)})
    assert preview_res["article_count"] > 0

    proc.stdin.close()
    proc.wait(timeout=5)


def test_engine_serve_subprocess_model_methods(tmp_path: Path) -> None:
    """Subprocess protocol test for model.detect, model.add, model.list, model.test."""
    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"
    env["CORPUSSIEVE_CONFIG_DIR"] = str(tmp_path / "config")

    proc = subprocess.Popen(
        [sys.executable, "-m", "corpussieve.cli.main", "engine", "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    def call(req_id: int, method: str, params: dict) -> dict:
        req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        proc.stdin.write(json.dumps(req) + "\n")  # type: ignore[union-attr]
        proc.stdin.flush()  # type: ignore[union-attr]
        line = proc.stdout.readline()  # type: ignore[union-attr]
        if not line:
            stderr_text = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Engine serve exited/crashed. Stderr:\n{stderr_text}")
        resp = json.loads(line)
        assert "error" not in resp or resp["error"] is None, resp.get("error")
        return resp["result"]

    call(1, "engine.hello", {})

    detect_res = call(2, "model.detect", {})
    assert isinstance(detect_res, list)

    add_res = call(3, "model.add", {"url": "http://127.0.0.1:11434", "provider": "ollama"})
    assert add_res["status"] == "added"
    assert add_res["base_url"] == "http://127.0.0.1:11434"

    list_res = call(4, "model.list", {})
    assert isinstance(list_res, list)

    # model.test against unconfigured/offline endpoint will return cap result
    test_res = call(
        5,
        "model.test",
        {
            "provider": "ollama",
            "endpoint": "http://127.0.0.1:11434",
            "model": "llama3",
        },
    )
    assert "status" in test_res or "model_id" in test_res

    proc.stdin.close()
    proc.wait(timeout=5)


def test_engine_serve_subprocess_ai_domain_methods(tmp_path: Path) -> None:
    """Subprocess protocol test for domain AI-assist methods."""
    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"

    proj_dir = tmp_path / "proj"
    proj_dir.mkdir(parents=True)
    domain_path = proj_dir / "domain.yaml"

    proc = subprocess.Popen(
        [sys.executable, "-m", "corpussieve.cli.main", "engine", "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    def raw_call(req_id: int, method: str, params: dict) -> dict:
        req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        proc.stdin.write(json.dumps(req) + "\n")  # type: ignore[union-attr]
        proc.stdin.flush()  # type: ignore[union-attr]
        line = proc.stdout.readline()  # type: ignore[union-attr]
        if not line:
            stderr_text = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Engine serve exited/crashed. Stderr:\n{stderr_text}")
        return json.loads(line)

    raw_call(1, "engine.hello", {})

    # 1. Test domain.create
    c_res = raw_call(
        2,
        "domain.create",
        {
            "project_dir": str(proj_dir),
            "name": "Test Domain",
            "language": "en",
            "intent": "Test intent",
            "roots": ["Video_games"],
            "max_depth": 3,
        },
    )
    assert "result" in c_res

    # 2. Test domain.applyAnswers (folds answers into domain.yaml)
    questions = [
        {
            "id": "q1",
            "question": "Include retro games?",
            "recommended": "include",
            "facet_target": "retro-games",
        }
    ]
    answers = {"q1": "include"}

    apply_res = raw_call(
        3,
        "domain.applyAnswers",
        {
            "domain": str(domain_path),
            "project_dir": str(proj_dir),
            "questions": questions,
            "answers": answers,
        },
    )
    assert "result" in apply_res
    res_data = apply_res["result"]
    assert "retro-games" in res_data["facets"]["include"]

    # 3. Test domain.proposeFacets & domain.boundaryQuestions against an
    # endpoint nothing listens on. This must NOT be Ollama's real default
    # port (11434): on a dev machine with Ollama actually running there,
    # that would silently exercise the live model instead of the offline
    # failure path, making the test flaky/slow depending on host state.
    unreachable = "http://127.0.0.1:59999"
    prop_res = raw_call(
        4,
        "domain.proposeFacets",
        {"intent": "Video games", "endpoint": unreachable},
    )
    assert "error" in prop_res
    assert prop_res["error"]["data"]["code"] == "MODEL_SCHEMA_TEST_FAILED"

    bq_res = raw_call(
        5,
        "domain.boundaryQuestions",
        {
            "intent": "Video games",
            "facets": {"include_facets": ["retro"], "exclude_facets": [], "rationale": ""},
            "endpoint": unreachable,
        },
    )
    assert "error" in bq_res
    assert bq_res["error"]["data"]["code"] == "MODEL_SCHEMA_TEST_FAILED"

    # 4. Test domain.create with exclude_facets round-trips into DomainFacets.exclude
    c_res2 = raw_call(
        6,
        "domain.create",
        {
            "project_dir": str(proj_dir),
            "name": "Test Domain",
            "language": "en",
            "intent": "Test intent",
            "roots": ["Video_games"],
            "max_depth": 3,
            "facets": ["retro"],
            "exclude_facets": ["esports"],
        },
    )
    assert "result" in c_res2
    written = yaml.safe_load(domain_path.read_text(encoding="utf-8"))
    assert written["facets"]["include"] == ["retro"]
    assert written["facets"]["exclude"] == ["esports"]

    proc.stdin.close()
    proc.wait(timeout=5)
