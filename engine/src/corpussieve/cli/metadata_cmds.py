from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml  # type: ignore[import-untyped]
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from corpussieve.cli._runner import handle_cli_action
from corpussieve.contracts.enums import JobState
from corpussieve.contracts.events import ProgressEvent
from corpussieve.contracts.project import ProjectFile
from corpussieve.metadata.build import build_metadata_index
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.sources.wikimedia.adapter import WikimediaXmlDumpAdapter

metadata_app = typer.Typer(help="Build and search source metadata indices")
console = Console()


@metadata_app.command("build")
def metadata_build(
    source: Annotated[
        Path,
        typer.Option(
            "--source",
            "-s",
            help="Path to source dump directory or file",
            exists=True,
        ),
    ],
    project_dir: Annotated[
        Path,
        typer.Option(
            "--project-dir",
            "-p",
            help="Path to project directory",
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
    """Build local SQLite metadata index from source dumps and update project.yaml."""

    def _action() -> dict[str, Any]:
        project_dir.mkdir(parents=True, exist_ok=True)
        db_path = project_dir / "cache" / "metadata.sqlite"
        project_yaml_path = project_dir / "project.yaml"

        adapter = WikimediaXmlDumpAdapter(source)
        inspection = adapter.inspect()

        # Manage project.yaml state transitions
        now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        if project_yaml_path.exists():
            with project_yaml_path.open("r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}
            project = ProjectFile.model_validate(raw_data)
            project.source_fingerprint = inspection.fingerprint.fingerprint
            project.job_state = JobState.METADATA_INDEXING
        else:
            project = ProjectFile(
                project_id=f"proj-{inspection.fingerprint.project}",
                name=f"{inspection.fingerprint.project} Project",
                created_at=now_iso,
                source_paths=[str(Path(source).resolve())],
                source_adapter="wikimedia_xml_dump",
                source_fingerprint=inspection.fingerprint.fingerprint,
                domain_path="domain.yaml",
                lock_path="domain.lock.json",
                output_dir="output",
                job_state=JobState.METADATA_INDEXING,
            )

        # Save state: METADATA_INDEXING
        _save_project(project_yaml_path, project)

        # Progress handler
        def _on_progress(event: ProgressEvent) -> None:
            if not json_output:
                console.print(f"[dim]{event.stage}: {event.message}[/dim]")

        if not json_output:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as p:
                p.add_task("Building metadata SQLite index...", total=None)
                build_metadata_index(adapter, db_path, progress=_on_progress)
        else:
            build_metadata_index(adapter, db_path, progress=_on_progress)

        # Update state: METADATA_READY
        project.job_state = JobState.METADATA_READY
        _save_project(project_yaml_path, project)

        with MetadataIndex(db_path) as idx:
            stats = idx.stats()

        res = {
            "status": "success",
            "db_path": str(db_path),
            "job_state": str(project.job_state),
            "stats": {
                "page_count": stats.page_count,
                "category_count": stats.category_count,
                "edge_count": stats.edge_count,
            },
        }

        if not json_output:
            console.print(
                f"[bold green]Build complete![/bold green] Database: [cyan]{db_path}[/cyan]"
            )
            console.print(f"Pages: {stats.page_count:,} | Categories: {stats.category_count:,}")

        return res

    handle_cli_action(_action, json_output=json_output, debug=debug, project_dir=project_dir)


@metadata_app.command("search")
def metadata_search(
    query: Annotated[str, typer.Argument(help="Category query substring")],
    project_dir: Annotated[
        Path,
        typer.Option(
            "--project-dir",
            "-p",
            help="Path to project directory",
        ),
    ],
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum search results"),
    ] = 25,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable JSON"),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable verbose debug logging"),
    ] = False,
) -> None:
    """Search category index by substring query."""

    def _action() -> list[dict[str, Any]]:
        db_path = project_dir / "cache" / "metadata.sqlite"
        with MetadataIndex(db_path) as idx:
            hits = idx.search_categories(query, limit=limit)

        results = [
            {
                "category": h.category,
                "direct_page_count": h.direct_page_count,
                "subcat_count": h.subcat_count,
            }
            for h in hits
        ]

        if not json_output:
            table = Table(title=f"Category Search Results for '{query}'")
            table.add_column("Category Name", style="cyan")
            table.add_column("Direct Pages", justify="right")
            table.add_column("Subcategories", justify="right")

            for h in hits:
                table.add_row(h.category, f"{h.direct_page_count:,}", f"{h.subcat_count:,}")

            console.print(table)

        return results

    handle_cli_action(_action, json_output=json_output, debug=debug, project_dir=project_dir)


def _save_project(path: Path, project: ProjectFile) -> None:
    data = project.model_dump(mode="json")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
