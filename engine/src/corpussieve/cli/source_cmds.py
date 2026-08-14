from pathlib import Path
from typing import Annotated, Any, Literal

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


@source_app.command("purge")
def source_purge(
    project: Annotated[
        Path,
        typer.Option("--project", "-p", help="Path to project directory", exists=True),
    ],
    confirm_deletes: Annotated[
        bool,
        typer.Option(
            "--i-understand-this-deletes-the-source",
            help="Mandatory non-interactive safety acknowledgment flag",
        ),
    ] = False,
    confirm_name: Annotated[
        str | None,
        typer.Option("--confirm-name", help="Typed project name confirmation"),
    ] = None,
    mode: Annotated[
        str,
        typer.Option("--mode", help="Purge deletion mode: 'trash' or 'permanent'"),
    ] = "trash",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable JSON"),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable verbose debug logging"),
    ] = False,
) -> None:
    """Purge raw source dump files after verifying corpus integrity."""

    def _action() -> Any:
        from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
        from corpussieve.safety.preconditions import check_purge_preconditions
        from corpussieve.safety.purge import execute_purge

        plan, blockers = check_purge_preconditions(project)
        if blockers or not plan:
            msgs = ", ".join(b.message for b in blockers)
            raise CorpusSieveError(
                ErrorCode.PURGE_OUTPUT_UNVERIFIED,
                f"Purge blocked: {msgs}",
            )

        if not confirm_deletes or not confirm_name:
            if not json_output:
                mb = plan.total_bytes / (1024 * 1024)
                cnt = len(plan.files_to_delete)
                msg_warn = f"[bold red]WARNING:[/bold red] Purge removes {cnt} files ({mb:.1f} MB)."
                console.print(msg_warn)
                console.print("Canonical corpus will remain intact.")
                c_name = typer.prompt(f"Type project name '{plan.project_name}' to confirm purge")
                if c_name != plan.project_name:
                    console.print("[bold red]Confirmation failed.[/bold red]")
                    raise typer.Exit(code=2)
                p_confirm_name = c_name
            else:
                msg = "Non-interactive purge requires --confirm-name and confirmation flag"
                raise CorpusSieveError(
                    ErrorCode.INTERNAL_ERROR,
                    msg,
                )
        else:
            p_confirm_name = confirm_name

        purge_mode: Literal["trash", "permanent"] = "permanent" if mode == "permanent" else "trash"
        res = execute_purge(plan, mode=purge_mode, confirm_token=p_confirm_name)
        if not json_output:
            f_mb = res.freed_bytes / (1024 * 1024)
            console.print(
                f"[bold green]Purge Complete![/bold green] Freed {f_mb:.1f} MB in {res.mode} mode."
            )
        return res.model_dump(mode="json")

    handle_cli_action(_action, json_output=json_output, debug=debug, project_dir=project)
