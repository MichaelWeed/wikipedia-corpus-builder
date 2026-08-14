import json
from pathlib import Path

from typer.testing import CliRunner

from corpussieve.cli.main import app

runner = CliRunner()


def test_cli_export_markdown_and_jsonl(tmp_path: Path) -> None:
    # Use existing fixoutput corpus generated earlier in tests
    corpus_dir = Path(__file__).resolve().parent.parent / "fixtures" / "fixoutput" / "corpus"
    if not corpus_dir.exists():
        # Fallback to scratch/fixoutput/corpus if available
        parent_dir = Path(__file__).resolve().parent.parent.parent
        corpus_dir = parent_dir / "scratch" / "fixoutput" / "corpus"

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
