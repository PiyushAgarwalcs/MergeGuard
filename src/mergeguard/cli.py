# mergeguard.cli
# Provides the command-line entrypoints for review, watch, serve, eval and report actions.

from __future__ import annotations

import json
import uuid
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
from mergeguard.storage import get_events, get_run, insert_finding, insert_run, list_runs
from mergeguard.tracing import record, span

console = Console()
app = typer.Typer(add_completion=False, help="MergeGuard CLI")
runs_app = typer.Typer(help="Inspect saved review traces")
app.add_typer(runs_app, name="runs")


def _run_id_from_diff(diff_file: Path) -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


@app.command()
def review(diff_file: Path) -> None:
    "Review a unified diff file and print the decision outcome."
    raw_text = diff_file.read_text(encoding="utf-8", errors="replace")
    run_id = _run_id_from_diff(diff_file)
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
    insert_run(
        run_id,
        repo=pr.repo,
        pr_number=pr.number,
        head_sha=pr.head_sha,
        status="running",
        outcome="pending",
    )
    context = ReviewContext(ci_status="passing", blocks=[])
    with span(run_id, "review", repo=pr.repo, pr_number=pr.number, head_sha=pr.head_sha):
        state: dict[str, object] = {
            "pr": pr,
            "context": context,
            "findings": scan_diff(raw_text),
        }
        record(
            run_id, "review", "scan", {"finding_count": len(cast(list[Finding], state["findings"]))}
        )
        findings = cast(list[Finding], state["findings"])
        verified, _ = verify_findings(findings, raw_text, cast(ReviewContext, state["context"]))
        merged = merge_findings(verified)
        state["findings"] = merged
        for finding in merged:
            insert_finding(run_id, finding.model_dump())
            record(
                run_id,
                "review",
                "finding",
                {
                    "id": finding.id,
                    "category": finding.category,
                    "severity": finding.severity.value,
                },
            )
        decision = judge_run(state)["decision"]
        record(
            run_id,
            "review",
            "decision",
            {
                "outcome": decision.outcome,
                "risk_score": decision.risk_score,
                "reasons": decision.reasons,
            },
        )
        insert_run(
            run_id,
            repo=pr.repo,
            pr_number=pr.number,
            head_sha=pr.head_sha,
            finished_at="now",
            status="finished",
            outcome=decision.outcome,
            total_ms=0,
        )

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
