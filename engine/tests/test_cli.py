from typer.testing import CliRunner

from corpussieve.cli.main import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "corpussieve 0.1.0.dev0" in result.output


def test_cli_domain_help() -> None:
    result = runner.invoke(app, ["domain", "--help"])
    assert result.exit_code == 0
    assert "Create, compile, audit, and preview domain definitions" in result.output
