import json
import os
import subprocess
import sys
from pathlib import Path

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


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
