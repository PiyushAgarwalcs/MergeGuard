# mergeguard.cli
# Provides the command-line entrypoints for review, watch, serve, eval and report actions.

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich.console import Console
from rich.table import Table

from evals.report import DEFAULT_REPORT_PATH, write_static_report
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.graph import build_graph
from mergeguard.models import Decision, Finding, PullRequest
from mergeguard.storage import connect, get_events, get_run, insert_finding, insert_run, list_runs
from mergeguard.tracing import record, span

console = Console()
app = typer.Typer(add_completion=False, help="MergeGuard CLI")
runs_app = typer.Typer(help="Inspect saved review traces")
eval_app = typer.Typer(help="Run and report evaluation suites")
app.add_typer(runs_app, name="runs")
app.add_typer(eval_app, name="eval")


def _run_id_from_diff(diff_file: Path) -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


async def _invoke_review_graph(
    state: dict[str, Any], database_path: str, thread_id: str
) -> dict[str, Any]:
    """Run the review graph with the async SQLite checkpoint saver."""
    async with AsyncSqliteSaver.from_conn_string(database_path) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer=checkpointer)
        return cast(
            dict[str, Any],
            await graph.ainvoke(
                state,
                config={"configurable": {"thread_id": thread_id}},
            ),
        )


@app.command()
def review(diff_file: Path) -> None:
    "Review a unified diff file and print the decision outcome."
    raw_text = diff_file.read_text(encoding="utf-8", errors="replace")
    run_id = _run_id_from_diff(diff_file)
    head_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    changed_files = sorted({hunk.file for hunk in parse_diff(raw_text)})
    pr = PullRequest(
        repo="local",
        number=0,
        head_sha=head_sha,
        base_sha="base-sha",
        title="review",
        body="",
        author="local",
        diff=raw_text,
        files=changed_files,
    )
    insert_run(
        run_id,
        repo=pr.repo,
        pr_number=pr.number,
        head_sha=pr.head_sha,
        status="running",
        outcome="pending",
    )
    started = time.perf_counter()
    with span(run_id, "review", repo=pr.repo, pr_number=pr.number, head_sha=pr.head_sha):
        graph_state: dict[str, Any] = {
            "pr": pr,
            "repo_path": str(Path.cwd()),
            "run_id": run_id,
            "ci_status": "missing",
            "incomplete": False,
        }
        checkpoint_connection = connect()
        database_path = str(checkpoint_connection.execute("PRAGMA database_list").fetchone()[2])
        checkpoint_connection.close()
        result = asyncio.run(
            _invoke_review_graph(
                graph_state,
                database_path,
                f"{pr.repo}#{pr.number}@{pr.head_sha}",
            )
        )

        findings = cast(list[Finding], result.get("decision_findings", []))
        decision = cast(Decision, result["decision"])
        for finding in cast(list[Finding], result.get("verified_findings", [])):
            status = "shown" if finding in findings else "dismissed"
            stored = {**finding.model_dump(), "verified": True, "status": status}
            insert_finding(run_id, stored)
            record(
                run_id,
                "review",
                "finding" if status == "shown" else "dismissed_finding",
                {
                    "id": finding.id,
                    "category": finding.category,
                    "severity": finding.severity.value,
                    "status": status,
                },
            )
        for rejection in result.get("rejected", []):
            record(
                run_id,
                "review",
                "finding_rejected",
                {"id": rejection.finding.id, "reason": rejection.reason},
            )
        record(run_id, "review", "scan", {"finding_count": len(result.get("findings", []))})
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
            total_ms=int((time.perf_counter() - started) * 1000),
        )

    table = Table(title=f"Decision: {decision.outcome.upper()}")
    table.add_column("Result")
    table.add_column("Details")
    table.add_row(
        decision.outcome, " | ".join(decision.reasons) if decision.reasons else "No findings"
    )
    for finding in findings:
        table.add_row(f"{finding.file}:{finding.line_start}", finding.category)
    console.print(table)
    if result.get("report"):
        console.print(str(result["report"]))

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


@eval_app.command("report")
def eval_report(
    output: Annotated[Path, typer.Option(help="HTML report destination.")] = DEFAULT_REPORT_PATH,
) -> None:
    """Write a static HTML summary of the latest evaluation per layer."""
    report_path = write_static_report(output)
    typer.echo(f"Wrote evaluation report to {report_path}")
