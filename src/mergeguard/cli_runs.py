# mergeguard.cli_runs
# Registers commands for listing saved review runs and showing their traces.

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from mergeguard.storage import get_events, get_run, list_runs


def register(runs_app: typer.Typer) -> None:
    """Attach operational run inspection commands to the supplied Typer app."""
    console = Console()

    @runs_app.command("list")
    def runs_list() -> None:
        rows = list_runs()
        if not rows:
            typer.echo("No runs recorded yet.")
            return
        table = Table(title="Saved runs")
        table.add_column("Run ID")
        table.add_column("Status")
        table.add_column("Outcome")
        table.add_column("Repo")
        for row in rows:
            table.add_row(
                str(row.get("run_id", "-")),
                str(row.get("status", "-")),
                str(row.get("outcome", "-")),
                str(row.get("repo", "-")),
            )
        console.print(table)

    @runs_app.command("show")
    def runs_show(run_id: str) -> None:
        run = get_run(run_id)
        if run is None:
            typer.echo(f"Run not found: {run_id}")
            raise typer.Exit(code=1)
        typer.echo(f"Run: {run_id}")
        typer.echo(json.dumps(run, sort_keys=True, default=str))
        for event in get_events(run_id):
            typer.echo(json.dumps(event, sort_keys=True, default=str))
