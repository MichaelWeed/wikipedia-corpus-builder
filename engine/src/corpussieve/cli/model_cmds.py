from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from corpussieve.cli._runner import handle_cli_action
from corpussieve.contracts.providers import ProviderEndpoint
from corpussieve.models.capability import run_capability_test
from corpussieve.models.config import (
    load_configured_endpoints,
    save_configured_endpoints,
)
from corpussieve.models.registry import detect_all, provider_for

model_app = typer.Typer(help="Detect, configure, and test local AI providers")
console = Console()


@model_app.command("detect")
def model_detect(
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Detect available local AI model providers (Ollama and LM Studio)."""

    def _action() -> list[dict[str, Any]]:
        endpoints = detect_all()
        results: list[dict[str, Any]] = []

        for ep in endpoints:
            try:
                p = provider_for(ep)
                models = p.list_models()
                results.append(
                    {
                        "provider": ep.provider,
                        "base_url": ep.base_url,
                        "is_loopback": ep.is_loopback,
                        "reachable": True,
                        "model_count": len(models),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "provider": ep.provider,
                        "base_url": ep.base_url,
                        "is_loopback": ep.is_loopback,
                        "reachable": False,
                        "error": str(e),
                    }
                )

        if not json_output:
            if not results:
                console.print("[yellow]No local AI model providers detected.[/yellow]")
                console.print("Hints: Ensure Ollama (11434) or LM Studio (1234) is running.")
            else:
                table = Table(title="Detected Local Model Providers")
                table.add_column("Provider", style="cyan")
                table.add_column("Base URL", style="magenta")
                table.add_column("Reachable", justify="center")
                table.add_column("Models", justify="right")

                for r in results:
                    table.add_row(
                        r["provider"],
                        r["base_url"],
                        "[green]Yes[/green]" if r["reachable"] else "[red]No[/red]",
                        str(r.get("model_count", 0)),
                    )
                console.print(table)

        return results

    handle_cli_action(_action, json_output=json_output, debug=debug)


@model_app.command("add")
def model_add(
    url: Annotated[str, typer.Option("--url", "-u", help="Base URL of provider endpoint")],
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="Provider type (ollama or lmstudio)"),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Add a custom provider endpoint URL to local configuration."""

    def _action() -> dict[str, Any]:
        is_loop = "127.0.0.1" in url or "localhost" in url
        prov_type = provider or ("ollama" if "11434" in url else "lmstudio")

        if not is_loop and not json_output:
            console.print(
                "[bold yellow]Privacy Note:[/bold yellow] Non-loopback endpoint configured."
            )

        ep = ProviderEndpoint(
            provider="ollama" if prov_type == "ollama" else "lmstudio",
            base_url=url,
            is_loopback=is_loop,
        )

        existing = load_configured_endpoints()
        filtered = [e for e in existing if e.base_url != url]
        filtered.append(ep)
        save_configured_endpoints(filtered)

        res = {
            "status": "added",
            "provider": ep.provider,
            "base_url": ep.base_url,
            "is_loopback": ep.is_loopback,
        }

        if not json_output:
            console.print(f"[bold green]Added provider endpoint:[/bold green] {url}")

        return res

    handle_cli_action(_action, json_output=json_output, debug=debug)


@model_app.command("list")
def model_list(
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """List all configured provider endpoints and their available models."""

    def _action() -> list[dict[str, Any]]:
        endpoints = load_configured_endpoints()
        if not endpoints:
            endpoints = detect_all()

        all_models: list[dict[str, Any]] = []

        for ep in endpoints:
            try:
                p = provider_for(ep)
                models = p.list_models()
                for mod_info in models:
                    all_models.append(
                        {
                            "provider": ep.provider,
                            "base_url": ep.base_url,
                            "model_id": mod_info.model_id,
                            "loaded": mod_info.loaded,
                            "model_type": mod_info.model_type,
                            "capability": mod_info.capability_result,
                        }
                    )
            except Exception as e:
                all_models.append(
                    {
                        "provider": ep.provider,
                        "base_url": ep.base_url,
                        "error": str(e),
                    }
                )

        if not json_output:
            table = Table(title="Available AI Models")
            table.add_column("Provider", style="cyan")
            table.add_column("Model ID", style="bold green")
            table.add_column("Loaded", justify="center")

            for m in all_models:
                if "error" not in m:
                    table.add_row(
                        m["provider"],
                        m["model_id"],
                        "[green]Yes[/green]" if m["loaded"] else "No",
                    )

            console.print(table)

        return all_models

    handle_cli_action(_action, json_output=json_output, debug=debug)


@model_app.command("test")
def model_test(
    model: Annotated[str, typer.Option("--model", "-m", help="Model ID to test")],
    endpoint: Annotated[
        str | None,
        typer.Option("--endpoint", "-e", help="Optional endpoint URL"),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Test model capability for structured JSON completion."""

    def _action() -> dict[str, Any]:
        endpoints = load_configured_endpoints() or detect_all()
        target_ep = None

        if endpoint:
            target_ep = next((e for e in endpoints if e.base_url == endpoint), None)

        if not target_ep and endpoints:
            target_ep = endpoints[0]

        if not target_ep:
            target_ep = ProviderEndpoint(
                provider="ollama", base_url="http://127.0.0.1:11434", is_loopback=True
            )

        p = provider_for(target_ep)
        cap = run_capability_test(p, model)

        res = cap.model_dump(mode="json")

        if not json_output:
            status_color = "green" if cap.status == "passed" else "red"
            console.print(f"Model Test: [{status_color}]{cap.status.upper()}[/{status_color}]")

        return res

    handle_cli_action(_action, json_output=json_output, debug=debug)
