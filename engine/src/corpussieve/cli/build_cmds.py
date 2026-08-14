from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from corpussieve.cli._runner import handle_cli_action
from corpussieve.domain.lock_build import read_lock
from corpussieve.extraction.build import run_build
from corpussieve.jobs.state import JobStore
from corpussieve.validation.validate import validate_corpus

build_app = typer.Typer(help="Run and manage extraction builds")
validate_app = typer.Typer(help="Validate canonical corpora")
console = Console()


@build_app.command("run")
def build_run(
    domain: Annotated[
        Path,
        typer.Option("--domain", "-d", help="Path to domain.lock.json file", exists=True),
    ],
    project_dir: Annotated[
        Path, typer.Option("--project-dir", "-p", help="Path to project directory")
    ],
    output: Annotated[Path, typer.Option("--output", "-o", help="Path to build output directory")],
    resume: Annotated[
        bool, typer.Option("--resume", help="Resume an interrupted build job")
    ] = False,
    allow_low_disk: Annotated[
        bool, typer.Option("--allow-low-disk", help="Override free disk space preflight warning")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Run end-to-end extraction build from compiled domain lock."""

    def _action() -> dict[str, Any]:
        resume_job_id = None
        state_db = project_dir / "state.sqlite"
        if state_db.exists():
            store = JobStore(state_db)
            act = store.active_job("build")
            store.close()

            if act and act.get("interrupted") == 1:
                if not resume:
                    console.print(
                        "[bold red]Interrupted build exists.[/bold red] Pass --resume to continue."
                    )
                    raise typer.Exit(code=2)

                resume_job_id = str(act.get("job_id"))

        report = run_build(
            project_dir=project_dir,
            lock_path=domain,
            output_dir=output,
            allow_low_disk=allow_low_disk,
            resume_job_id=resume_job_id,
        )

        res = report.model_dump(mode="json")
        if not json_output:
            console.print(
                f"[bold green]Build complete![/bold green] Articles: {report.extraction_count:,}"
            )
        return res

    handle_cli_action(_action, json_output=json_output, debug=debug, project_dir=project_dir)


@validate_app.command("run")
def validate_run(
    corpus: Annotated[
        Path,
        typer.Option("--corpus", "-c", help="Path to promoted corpus directory", exists=True),
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable verbose debug logging")] = False,
) -> None:
    """Validate canonical corpus and manifest files."""

    def _action() -> dict[str, Any]:
        lock_file = corpus / "domain.lock.json"
        if not lock_file.exists():
            lock_file = corpus.parent / "domain.lock.json"

        lock = read_lock(lock_file)
        val_res = validate_corpus(corpus, lock)

        res = val_res.model_dump(mode="json")
        if not json_output:
            if val_res.status == "PASSED":
                console.print(
                    f"[bold green]Corpus Validated![/bold green] Records: {val_res.total_records:,}"
                )
            else:
                console.print(
                    f"[bold red]Corpus Validation Failed:[/bold red] {', '.join(val_res.errors)}"
                )
                raise typer.Exit(code=2)

        if val_res.status != "PASSED":
            raise typer.Exit(code=2)

        return res

    handle_cli_action(_action, json_output=json_output, debug=debug)
