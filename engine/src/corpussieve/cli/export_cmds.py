from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from corpussieve.cli._runner import handle_cli_action
from corpussieve.exporters.jsonl import export_jsonl
from corpussieve.exporters.markdown import export_markdown

export_app = typer.Typer(help="Export corpora to Markdown or JSONL formats")
console = Console()


@export_app.command("markdown")
def export_markdown_cmd(
    corpus: Annotated[
        Path,
        typer.Option("--corpus", "-c", help="Path to promoted corpus directory", exists=True),
    ],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Path to markdown output directory")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Export canonical corpus to RAG-ready Markdown files."""

    def _action() -> dict[str, Any]:
        res = export_markdown(corpus_dir=corpus, output_dir=output)
        if not json_output:
            console.print(
                f"[bold green]Export Complete![/bold green] Files: {res['exported_count']:,}"
            )
        return res

    handle_cli_action(_action, json_output=json_output, debug=debug)


@export_app.command("jsonl")
def export_jsonl_cmd(
    corpus: Annotated[
        Path,
        typer.Option("--corpus", "-c", help="Path to promoted corpus directory", exists=True),
    ],
    output: Annotated[Path, typer.Option("--output", "-o", help="Path to JSONL output directory")],
    normalized: Annotated[
        bool, typer.Option("--normalized", help="Export normalized Markdown content")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Export canonical corpus to plain uncompressed .jsonl file."""

    def _action() -> dict[str, Any]:
        res = export_jsonl(corpus_dir=corpus, output_dir=output, normalized=normalized)
        if not json_output:
            console.print(
                f"[bold green]Export Complete![/bold green] Records: {res['exported_count']:,}"
            )
        return res

    handle_cli_action(_action, json_output=json_output, debug=debug)
