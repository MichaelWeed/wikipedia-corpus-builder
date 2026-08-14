import typer

from corpussieve import __version__

app = typer.Typer(
    name="corpussieve",
    help="Deterministic domain-specific Wikitext corpus compiler",
    no_args_is_help=True,
)

project_app = typer.Typer(help="Manage CorpusSieve projects")
source_app = typer.Typer(help="Inspect and manage dump sources")
metadata_app = typer.Typer(help="Build and search source metadata indices")
model_app = typer.Typer(help="Detect and test local AI providers")
domain_app = typer.Typer(help="Create, compile, audit, and preview domain definitions")
build_app = typer.Typer(help="Run and manage extraction builds")
validate_app = typer.Typer(help="Validate canonical corpora")
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
