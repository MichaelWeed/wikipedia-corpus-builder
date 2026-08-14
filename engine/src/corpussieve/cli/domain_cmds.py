from pathlib import Path
from typing import Annotated, Any

import typer
import yaml  # type: ignore[import-untyped]
from rich.console import Console
from rich.table import Table

from corpussieve.cli._runner import handle_cli_action
from corpussieve.contracts.domain import DomainDefinition, DomainPolicy, DomainRoot
from corpussieve.contracts.enums import JobState
from corpussieve.contracts.project import ProjectFile
from corpussieve.domain.definition import load_domain, save_domain
from corpussieve.domain.lock_build import compile_lock, read_lock, verify_lock, write_lock
from corpussieve.domain.manifest_io import write_manifest
from corpussieve.domain.preview import build_preview, explain_page
from corpussieve.domain.select import select_articles
from corpussieve.metadata.queries import MetadataIndex

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


@domain_app.command("compile")
def domain_compile(
    domain: Annotated[
        Path,
        typer.Option("--domain", "-d", help="Path to domain YAML definition file", exists=True),
    ],
    project_dir: Annotated[
        Path, typer.Option("--project-dir", "-p", help="Path to project directory")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Compile domain definition against SQLite metadata index into domain.lock.json."""

    def _action() -> dict[str, Any]:
        defn = load_domain(domain)
        db_path = project_dir / "cache" / "metadata.sqlite"

        with MetadataIndex(db_path) as idx:
            stats = idx.stats()
            lock, traversal = compile_lock(defn, idx, stats.source_fingerprint)

        lock_path = domain.with_name(f"{domain.stem}.lock.json")
        write_lock(lock, lock_path)

        # Also write to DIR/domain.lock.json for standard project layout
        project_lock_path = project_dir / "domain.lock.json"
        write_lock(lock, project_lock_path)

        # Update project.yaml state
        project_yaml_path = project_dir / "project.yaml"
        _update_project_state(project_yaml_path, JobState.DOMAIN_COMPILED)

        res = {
            "status": "success",
            "domain_id": defn.id,
            "lock_path": str(lock_path),
            "lock_hash": lock.lock_hash,
            "included_categories_count": len(traversal.included),
            "decisions_count": len(lock.category_decisions),
            "warnings_count": len(traversal.warnings),
        }

        if not json_output:
            console.print(
                f"[bold green]Domain compiled![/bold green] Lock: [cyan]{lock_path}[/cyan]"
            )
            console.print(
                f"Lock Hash: [dim]{lock.lock_hash}[/dim] | Included Cats: {len(traversal.included)}"
            )

        return res

    handle_cli_action(_action, json_output=json_output, debug=debug, project_dir=project_dir)


@domain_app.command("preview")
def domain_preview(
    domain: Annotated[
        Path,
        typer.Option("--domain", "-d", help="Path to domain YAML definition file", exists=True),
    ],
    project_dir: Annotated[
        Path, typer.Option("--project-dir", "-p", help="Path to project directory")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Build article selection preview and manifest from compiled domain definition."""

    def _action() -> Any:
        defn = load_domain(domain)
        db_path = project_dir / "cache" / "metadata.sqlite"

        with MetadataIndex(db_path) as idx:
            stats = idx.stats()
            lock, traversal = compile_lock(defn, idx, stats.source_fingerprint)
            records, _ = select_articles(idx, traversal, defn)

            # Write manifest preview
            manifest_path = project_dir / "cache" / "manifest.preview.jsonl.zst"
            write_manifest(records, manifest_path)

            preview = build_preview(idx, lock, traversal, records, defn)

        # Update project.yaml state
        project_yaml_path = project_dir / "project.yaml"
        _update_project_state(project_yaml_path, JobState.PREVIEWED)

        if not json_output:
            table = Table(title=f"Domain Preview — {defn.name} ({defn.id})")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Target Article Count", f"{preview.article_count:,}")
            table.add_row(
                "Estimated Output Size",
                f"{preview.estimated_output_bytes / (1024 * 1024):.2f} MB",
            )
            table.add_row("Root Categories", f"{len(preview.counts_by_root)}")
            table.add_row("Warnings", f"{len(preview.warnings)}")

            console.print(table)
            if preview.sample_included:
                samples_str = ", ".join(preview.sample_included[:5])
                console.print(f"\n[bold]Sample Included Pages:[/bold] {samples_str}")

        return preview

    handle_cli_action(_action, json_output=json_output, debug=debug, project_dir=project_dir)


@domain_app.command("audit")
def domain_audit(
    domain: Annotated[
        Path,
        typer.Option("--domain", "-d", help="Path to domain YAML definition file", exists=True),
    ],
    project_dir: Annotated[
        Path, typer.Option("--project-dir", "-p", help="Path to project directory")
    ],
    page: Annotated[
        str | None,
        typer.Option("--page", help="Optional page title or ID to explain selection status"),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Verify lock integrity and explain article selection status."""

    def _action() -> Any:
        defn = load_domain(domain)
        db_path = project_dir / "cache" / "metadata.sqlite"
        lock_path = domain.with_name(f"{domain.stem}.lock.json")

        if not lock_path.exists():
            lock_path = project_dir / "domain.lock.json"

        lock = read_lock(lock_path)

        with MetadataIndex(db_path) as idx:
            stats = idx.stats()
            verify_errors = verify_lock(lock, defn, stats.source_fingerprint)

            if page:
                traversal = compile_lock(defn, idx, stats.source_fingerprint)[1]
                records, _ = select_articles(idx, traversal, defn)

                page_target: str | int = int(page) if page.isdigit() else page
                explain = explain_page(idx, lock, records, page_target, defn)

                if not json_output:
                    console.print(f"Target: {explain.target} | Status: {explain.status}")
                    console.print(f"Reason: {explain.reason}")
                    if explain.provenance_chain:
                        chain_str = " -> ".join(explain.provenance_chain)
                        console.print(f"Provenance Chain: {chain_str}")
                return explain

        res = {
            "status": "valid" if not verify_errors else "invalid",
            "domain_id": lock.domain_id,
            "lock_hash": lock.lock_hash,
            "verification_errors": verify_errors,
        }

        if not json_output:
            if not verify_errors:
                console.print(
                    f"[bold green]Lock verified![/bold green] Hash: [cyan]{lock.lock_hash}[/cyan]"
                )
            else:
                console.print(
                    f"[bold red]Lock verification failed:[/bold red] {', '.join(verify_errors)}"
                )

        return res

    handle_cli_action(_action, json_output=json_output, debug=debug, project_dir=project_dir)


def _update_project_state(path: Path, new_state: JobState) -> None:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}
    project = ProjectFile.model_validate(raw_data)
    project.job_state = new_state
    dump_data = yaml.safe_dump(project.model_dump(mode="json"), sort_keys=False)
    path.write_text(dump_data, encoding="utf-8")
