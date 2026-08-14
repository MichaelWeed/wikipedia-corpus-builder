import typer

from corpussieve import __version__
from corpussieve.cli.build_cmds import build_app, validate_app
from corpussieve.cli.domain_cmds import domain_app
from corpussieve.cli.metadata_cmds import metadata_app
from corpussieve.cli.model_cmds import model_app
from corpussieve.cli.source_cmds import source_app

app = typer.Typer(
    name="corpussieve",
    help="Deterministic domain-specific Wikitext corpus compiler",
    no_args_is_help=True,
)

project_app = typer.Typer(help="Manage CorpusSieve projects")
export_app = typer.Typer(help="Export corpora to Markdown or JSONL")

app.add_typer(project_app, name="project")
app.add_typer(source_app, name="source")
app.add_typer(metadata_app, name="metadata")
app.add_typer(model_app, name="model")
app.add_typer(domain_app, name="domain")
app.add_typer(build_app, name="build")
app.add_typer(validate_app, name="validate")
app.add_typer(export_app, name="export")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"corpussieve {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """CorpusSieve CLI entrypoint."""


def app_entry() -> None:
    app()
