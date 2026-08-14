from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from corpussieve.cli._runner import handle_cli_action
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

source_app = typer.Typer(help="Inspect and manage dump sources")
console = Console()


@source_app.command("inspect")
def source_inspect(
    source: Annotated[
        Path,
        typer.Option(
            "--source",
            "-s",
            help="Path to source dump file or directory",
            exists=True,
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable JSON"),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable verbose debug logging"),
    ] = False,
) -> None:
    """Inspect local Wikimedia dump files and display dump kind, files, and warnings."""

    def _action() -> Any:
        adapter = WikimediaXmlDumpAdapter(source)
        inspection = adapter.inspect()

        if not json_output:
            fp = inspection.fingerprint
            table = Table(title=f"Source Inspection — {fp.project} ({fp.dump_date})")
            table.add_column("File Name", style="cyan")
            table.add_column("Size (Bytes)", justify="right")
            table.add_column("Quick Hash", style="dim")

            for f in inspection.fingerprint.files:
                table.add_row(f.name, f"{f.size_bytes:,}", f.quick_hash[:16] + "...")

            console.print(table)
            console.print(f"[bold]Dump Kind:[/bold] {inspection.dump_kind}")
            console.print(f"[bold]Fingerprint:[/bold] {inspection.fingerprint.fingerprint}")

            if inspection.warnings:
                console.print("\n[bold yellow]Warnings:[/bold yellow]")
                for w in inspection.warnings:
                    console.print(f" - [yellow]{w}[/yellow]")

        return inspection

    handle_cli_action(_action, json_output=json_output, debug=debug)
