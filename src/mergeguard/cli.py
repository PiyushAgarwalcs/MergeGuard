# mergeguard.cli
# Provides the command-line entrypoints for review, watch, serve, eval and report actions.

from __future__ import annotations

from pathlib import Path
from typing import cast

import typer
from rich.console import Console
from rich.table import Table

from mergeguard.checks.judge import judge_run
from mergeguard.checks.merge_findings import merge_findings
from mergeguard.checks.rule_scan import scan_diff
from mergeguard.checks.verify_findings import verify_findings
from mergeguard.models import Finding, PullRequest, ReviewContext

console = Console()
app = typer.Typer(add_completion=False, help="MergeGuard CLI")


@app.command()
def review(diff_file: Path) -> None:
    "Review a unified diff file and print the decision outcome."
    raw_text = diff_file.read_text(encoding="utf-8", errors="replace")
    pr = PullRequest(
        repo="local",
        number=0,
        head_sha="local-sha",
        base_sha="base-sha",
        title="review",
        body="",
        author="local",
        diff=raw_text,
        files=[str(diff_file)],
    )
    context = ReviewContext(ci_status="passing", blocks=[])
    state: dict[str, object] = {
        "pr": pr,
        "context": context,
        "findings": scan_diff(raw_text),
    }
    findings = cast(list[Finding], state["findings"])
    verified, _ = verify_findings(findings, raw_text, cast(ReviewContext, state["context"]))
    merged = merge_findings(verified)
    state["findings"] = merged
    decision = judge_run(state)["decision"]

    table = Table(title=f"Decision: {decision.outcome.upper()}")
    table.add_column("Result")
    table.add_column("Details")
    table.add_row(
        decision.outcome, " | ".join(decision.reasons) if decision.reasons else "No findings"
    )
    for finding in merged:
        table.add_row(f"{finding.file}:{finding.line_start}", finding.category)
    console.print(table)

    if decision.outcome == "block":
        raise typer.Exit(code=2)
    if decision.outcome == "needs_human":
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


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
