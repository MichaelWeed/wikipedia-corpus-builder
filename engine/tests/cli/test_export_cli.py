import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from corpussieve.cli.main import app
from corpussieve.contracts.domain import DomainDefinition, DomainRoot
from corpussieve.domain.definition import save_domain
from corpussieve.domain.lock_build import compile_lock, write_lock
from corpussieve.extraction.build import run_build
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

runner = CliRunner()

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def _build_real_corpus(tmp_path: Path) -> Path:
    """Runs the real fixwiki extraction pipeline and returns the resulting
    corpus dir. This test previously read a "fixoutput" corpus that no test
    in this repo generates or commits -- it only ever passed on a machine
    that happened to have one left over from some other ad-hoc run, and
    failed on every genuinely fresh checkout (including real CI, where it
    always fails). Building a real corpus here makes the test self-contained.
    """
    proj_dir = tmp_path / "proj"
    out_dir = tmp_path / "out"
    proj_dir.mkdir()
    out_dir.mkdir()

    source_dir = proj_dir / "source"
    shutil.copytree(FIXWIKI_DIR, source_dir)

    adapter = WikimediaXmlDumpAdapter(source_dir)
    db_path = proj_dir / "cache" / "metadata.sqlite"
    build_metadata_index(adapter, db_path)

    idx = MetadataIndex(db_path)
    fp = adapter.inspect().fingerprint.fingerprint
    defn = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games", max_depth=2)],
    )
    save_domain(defn, proj_dir / "domain.yaml")
    lock, _ = compile_lock(defn, idx, fp)
    lock_path = proj_dir / "domain.lock.json"
    write_lock(lock, lock_path)

    run_build(proj_dir, lock_path, out_dir, allow_low_disk=True)
    return out_dir / "corpus"


def test_cli_export_markdown_and_jsonl(tmp_path: Path) -> None:
    corpus_dir = _build_real_corpus(tmp_path)

    md_out = tmp_path / "export_md"
    jsonl_out = tmp_path / "export_jsonl"

    res_md = runner.invoke(
        app,
        [
            "export",
            "markdown",
            "--corpus",
            str(corpus_dir),
            "--output",
            str(md_out),
            "--json",
        ],
    )
    assert res_md.exit_code == 0
    md_data = json.loads(res_md.output)
    assert md_data["status"] == "PASSED"
    assert (md_out / "_index.json").exists()
    assert (md_out / "ATTRIBUTION.md").exists()

    res_jsonl = runner.invoke(
        app,
        [
            "export",
            "jsonl",
            "--corpus",
            str(corpus_dir),
            "--output",
            str(jsonl_out),
            "--normalized",
            "--json",
        ],
    )
    assert res_jsonl.exit_code == 0
    jsonl_data = json.loads(res_jsonl.output)
    assert jsonl_data["status"] == "PASSED"
    assert (jsonl_out / "corpus.normalized.jsonl").exists()
