import json
from pathlib import Path

from typer.testing import CliRunner

from corpussieve.cli.main import app

runner = CliRunner()
FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_source_inspect_human() -> None:
    result = runner.invoke(app, ["source", "inspect", "--source", str(FIXWIKI_DIR)])
    assert result.exit_code == 0
    assert "fixwiki" in result.output
    assert "Dump Kind:" in result.output


def test_source_inspect_json() -> None:
    result = runner.invoke(app, ["source", "inspect", "--source", str(FIXWIKI_DIR), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["adapter"] == "wikimedia_xml_dump"
    assert data["dump_kind"] == "multistream"
    assert data["fingerprint"]["project"] == "fixwiki"


def test_source_inspect_unsupported_json(tmp_path: Path) -> None:
    result = runner.invoke(app, ["source", "inspect", "--source", str(tmp_path), "--json"])
    assert result.exit_code == 2
    data = json.loads(result.output)
    assert data["error"]["code"] == "SOURCE_UNSUPPORTED"


def test_metadata_build_and_search_json(tmp_path: Path) -> None:
    proj_dir = tmp_path / "testproj"
    build_res = runner.invoke(
        app,
        [
            "metadata",
            "build",
            "--source",
            str(FIXWIKI_DIR),
            "--project-dir",
            str(proj_dir),
            "--json",
        ],
    )
    assert build_res.exit_code == 0
    build_data = json.loads(build_res.output)
    assert build_data["status"] == "success"
    assert build_data["job_state"] == "METADATA_READY"
    assert build_data["stats"]["page_count"] > 0

    # Search category
    search_res = runner.invoke(
        app,
        [
            "metadata",
            "search",
            "--project-dir",
            str(proj_dir),
            "games",
            "--json",
        ],
    )
    assert search_res.exit_code == 0
    search_data = json.loads(search_res.output)
    assert isinstance(search_data, list)
    assert len(search_data) > 0
    assert any("games" in hit["category"].lower() for hit in search_data)
