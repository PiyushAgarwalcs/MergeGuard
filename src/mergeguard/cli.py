# mergeguard.cli
# Provides the command-line entrypoints for review, watch, serve, eval and report actions.

from __future__ import annotations

import typer

app = typer.Typer(add_completion=False, help="MergeGuard CLI")


@app.command()
def review() -> None:
    typer.echo("review command placeholder")


@app.command()
def watch() -> None:
    typer.echo("watch command placeholder")


@app.command()
def serve() -> None:
    typer.echo("serve command placeholder")


@app.command()
def eval_fast() -> None:
    typer.echo("eval-fast command placeholder")


@app.command()
def report() -> None:
    typer.echo("report command placeholder")
