import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from corpussieve.cli.main import app

runner = CliRunner()
FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_cli_build_and_validate_flow(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"
    out_dir = tmp_path / "fixoutput"
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy source
    shutil.copytree(FIXWIKI_DIR, proj_dir / "source")

    # 2. Build metadata
    res_meta = runner.invoke(
        app,
        [
            "metadata",
            "build",
            "--source",
            str(proj_dir / "source"),
            "--project-dir",
            str(proj_dir),
            "--json",
        ],
    )
    assert res_meta.exit_code == 0

    # 3. Create & compile domain
    res_create = runner.invoke(
        app,
        [
            "domain",
            "create",
            "--id",
            "video-games",
            "--name",
            "Video_games",
            "--language",
            "en",
            "--project-dir",
            str(proj_dir),
            "--json",
        ],
    )
    assert res_create.exit_code == 0

    domain_file = proj_dir / "domains" / "video-games.yaml"
    res_compile = runner.invoke(
        app,
        [
            "domain",
            "compile",
            "--domain",
            str(domain_file),
            "--project-dir",
            str(proj_dir),
            "--json",
        ],
    )
    assert res_compile.exit_code == 0
    lock_file = proj_dir / "domains" / "video-games.lock.json"

    # 4. Build corpus
    res_build = runner.invoke(
        app,
        [
            "build",
            "run",
            "--domain",
            str(lock_file),
            "--project-dir",
            str(proj_dir),
            "--output",
            str(out_dir),
            "--allow-low-disk",
            "--json",
        ],
    )
    assert res_build.exit_code == 0
    build_data = json.loads(res_build.output)
    assert build_data["validation"] == "PASSED"

    # 5. Validate promoted corpus
    corpus_dir = out_dir / "corpus"
    res_val = runner.invoke(
        app,
        [
            "validate",
            "run",
            "--corpus",
            str(corpus_dir),
            "--json",
        ],
    )
    assert res_val.exit_code == 0
    val_data = json.loads(res_val.output)
    assert val_data["status"] == "PASSED"
