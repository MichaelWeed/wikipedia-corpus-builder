import json
from pathlib import Path

from typer.testing import CliRunner

from corpussieve.cli.main import app

runner = CliRunner()
FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_cli_domain_compile_preview_audit_flow(tmp_path: Path) -> None:
    proj_dir = tmp_path / "fixproj"

    # 1. Build metadata index first
    res_meta = runner.invoke(
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
    assert res_meta.exit_code == 0

    # 2. Create domain template
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
    created_domain_file = proj_dir / "domains" / "video-games.yaml"
    assert created_domain_file.exists()

    # 3. Compile domain
    res_compile = runner.invoke(
        app,
        [
            "domain",
            "compile",
            "--domain",
            str(created_domain_file),
            "--project-dir",
            str(proj_dir),
            "--json",
        ],
    )
    assert res_compile.exit_code == 0
    compile_data = json.loads(res_compile.output)
    assert compile_data["status"] == "success"
    assert len(compile_data["lock_hash"]) > 0

    # 4. Preview domain
    res_preview = runner.invoke(
        app,
        [
            "domain",
            "preview",
            "--domain",
            str(created_domain_file),
            "--project-dir",
            str(proj_dir),
            "--json",
        ],
    )
    assert res_preview.exit_code == 0
    preview_data = json.loads(res_preview.output)
    assert preview_data["article_count"] > 0

    # 5. Audit domain lock & explain page
    res_audit = runner.invoke(
        app,
        [
            "domain",
            "audit",
            "--domain",
            str(created_domain_file),
            "--project-dir",
            str(proj_dir),
            "--page",
            "Super_Mario_Bros",
            "--json",
        ],
    )
    assert res_audit.exit_code == 0
    audit_data = json.loads(res_audit.output)
    assert audit_data["target"] == "Super_Mario_Bros"
    assert audit_data["status"] == "included"
