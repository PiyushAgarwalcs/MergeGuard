# mergeguard.cli
# Provides the command-line entrypoints for review, watch, serve, eval and report actions.

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Annotated, Any, cast

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from evals.report import DEFAULT_REPORT_PATH, write_static_report
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.cli_runs import register as register_run_commands
from mergeguard.github import GitHubAPIError, GitHubClient
from mergeguard.models import Decision, Finding, PullRequest
from mergeguard.monitoring import shadow_report as build_shadow_report
from mergeguard.review_service import (
    _invoke_review_graph,
    _run_id_from_diff,
    parse_pull_request_target,  # noqa: F401 - public compatibility export
    review_pull_request,
)
from mergeguard.storage import (
    connect,
    insert_finding,
    insert_run,
)
from mergeguard.tracing import record, span
from mergeguard.watch_service import (
    _resume_waiting_review,  # noqa: F401 - used by the webhook dispatcher
    watch_repository_once,
)

console = Console()
app = typer.Typer(add_completion=False, help="MergeGuard CLI")
runs_app = typer.Typer(help="Inspect saved review traces")
eval_app = typer.Typer(help="Run and report evaluation suites")
app.add_typer(runs_app, name="runs")
register_run_commands(runs_app)
app.add_typer(eval_app, name="eval")


@app.command("shadow-report")
def shadow_report() -> None:
    """Summarize shadow reviews, category dismissal rates, and approvals after blocks."""
    typer.echo(json.dumps(build_shadow_report(), sort_keys=True, default=str))


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


@app.command("review-pr")
def review_pr(target: str) -> None:
    """Review owner/repo#number and publish the result to GitHub."""
    try:
        result = review_pull_request(target)
    except (GitHubAPIError, OSError, ValueError) as error:
        typer.echo(f"GitHub review failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    decision = result["decision"]
    typer.echo(f"{decision.outcome}: {target} (run {result['run_id']})")
    if decision.outcome == "block":
        raise typer.Exit(code=2)
    if decision.outcome == "needs_human":
        raise typer.Exit(code=1)


@app.command("watch")
def watch(
    repository: str,
    shadow: bool = typer.Option(
        False, "--shadow", help="Record reviews without publishing to GitHub."
    ),
    interval: int = typer.Option(60, "--interval", min=1, help="Polling interval in seconds."),
) -> None:
    """Poll open pull requests and resume waiting reviews from comments."""
    try:
        with GitHubClient() as client:
            while True:
                actions = watch_repository_once(repository, github_client=client, shadow=shadow)
                for action in actions:
                    typer.echo(json.dumps(action, sort_keys=True))
                time.sleep(interval)
    except KeyboardInterrupt:
        typer.echo("Stopped MergeGuard watch.")
    except (GitHubAPIError, OSError, ValueError) as error:
        typer.echo(f"GitHub watch failed: {error}", err=True)
        raise typer.Exit(code=1) from error


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Interface to bind the webhook server to."),
    port: int = typer.Option(8000, min=1, max=65535, help="Webhook server port."),
) -> None:
    """Run the FastAPI health and GitHub webhook service."""
    uvicorn.run("mergeguard.api:app", host=host, port=port)


@eval_app.command("report")
def eval_report(
    output: Annotated[Path, typer.Option(help="HTML report destination.")] = DEFAULT_REPORT_PATH,
) -> None:
    """Write a static HTML summary of the latest evaluation per layer."""
    report_path = write_static_report(output)
    typer.echo(f"Wrote evaluation report to {report_path}")
