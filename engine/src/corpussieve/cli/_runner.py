import json
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

from corpussieve.contracts.errors import CorpusSieveError

console_err = Console(stderr=True)


def handle_cli_action(
    action_fn: Callable[[], Any],
    json_output: bool = False,
    debug: bool = False,
    project_dir: Path | None = None,
) -> None:
    """Standard CLI error handling and execution wrapper.

    Exit Codes:
      0: Success
      2: CorpusSieveError (structured payload if --json)
      3: Unexpected Exception (logged to reports/last-error.log)
    """
    try:
        result = action_fn()
        if json_output:
            if hasattr(result, "model_dump_json"):
                typer.echo(result.model_dump_json(indent=2))
            elif isinstance(result, (dict, list)):
                typer.echo(json.dumps(result, indent=2))
            elif result is not None:
                typer.echo(str(result))
        raise typer.Exit(code=0)

    except CorpusSieveError as err:
        if json_output:
            err_payload = {
                "error": {
                    "code": str(err.code),
                    "message": err.message,
                    "detail": err.detail,
                }
            }
            typer.echo(json.dumps(err_payload, indent=2))
        else:
            console_err.print(
                Panel(
                    f"[bold red]Error [{err.code}]:[/bold red] {err.message}",
                    title="CorpusSieve Error",
                    border_style="red",
                )
            )
            if err.detail and debug:
                console_err.print(f"[yellow]Detail:[/yellow] {err.detail}")
        raise typer.Exit(code=2) from err

    except typer.Exit:
        raise

    except Exception as exc:
        log_dir = (project_dir / "reports") if project_dir else Path("reports")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "last-error.log"
            log_file.write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            log_file = Path("last-error.log")
            log_file.write_text(traceback.format_exc(), encoding="utf-8")

        if json_output:
            err_payload = {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                    "detail": {"log_file": str(log_file)},
                }
            }
            typer.echo(json.dumps(err_payload, indent=2))
        else:
            console_err.print(
                f"[bold red]Unexpected Error:[/bold red] {exc} (logged to {log_file})"
            )
            if debug:
                console_err.print(traceback.format_exc())

        raise typer.Exit(code=3) from exc
