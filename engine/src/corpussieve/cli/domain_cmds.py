from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from corpussieve.cli._runner import handle_cli_action
from corpussieve.contracts.domain import DomainDefinition, DomainPolicy, DomainRoot
from corpussieve.domain.definition import save_domain

domain_app = typer.Typer(help="Create, compile, audit, and preview domain definitions")
console = Console()


@domain_app.command("create")
def domain_create(
    domain_id: Annotated[str, typer.Option("--id", "-i", help="Domain unique identifier slug")],
    name: Annotated[str, typer.Option("--name", "-n", help="Human readable domain name")],
    language: Annotated[
        str, typer.Option("--language", "-l", help="Source Wikipedia language code (e.g. en)")
    ],
    project_dir: Annotated[
        Path, typer.Option("--project-dir", "-p", help="Path to project directory")
    ],
    intent: Annotated[
        str | None,
        typer.Option(
            "--intent",
            help="High-level text description of target domain (stored verbatim in description)",
        ),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Create a template domain definition YAML file under project_dir/domains/<id>.yaml."""

    def _action() -> dict[str, Any]:
        domain_dir = project_dir / "domains"
        domain_path = domain_dir / f"{domain_id}.yaml"

        defn = DomainDefinition(
            id=domain_id,
            name=name,
            language=language,
            description=intent or f"Domain definition for {name}",
            roots=[DomainRoot(query=f"Category:{name}", max_depth=3)],
            policy=DomainPolicy(),
        )

        save_domain(defn, domain_path)

        res = {
            "status": "created",
            "domain_id": domain_id,
            "domain_path": str(domain_path),
        }

        if not json_output:
            console.print(
                f"[bold green]Domain created![/bold green] File: [cyan]{domain_path}[/cyan]"
            )

        return res

    handle_cli_action(_action, json_output=json_output, debug=debug, project_dir=project_dir)
