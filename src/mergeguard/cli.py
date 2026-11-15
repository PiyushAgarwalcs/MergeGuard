# mergeguard.cli
# Provides the command-line entrypoints for review, watch, serve, eval and report actions.

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, cast

import httpx
import typer
import uvicorn
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich.console import Console
from rich.table import Table

from evals.report import DEFAULT_REPORT_PATH, write_static_report
from mergeguard.agents import reporter
from mergeguard.checks import human_gate
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.github import GitHubAPIError, GitHubClient
from mergeguard.graph import build_graph
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import Decision, Finding, PullRequest
from mergeguard.monitoring import shadow_report as build_shadow_report
from mergeguard.storage import (
    connect,
    find_review_run,
    get_events,
    get_run,
    insert_finding,
    insert_run,
    list_runs,
)
from mergeguard.tracing import record, span

console = Console()
app = typer.Typer(add_completion=False, help="MergeGuard CLI")
runs_app = typer.Typer(help="Inspect saved review traces")
eval_app = typer.Typer(help="Run and report evaluation suites")
app.add_typer(runs_app, name="runs")
app.add_typer(eval_app, name="eval")


@app.command("shadow-report")
def shadow_report() -> None:
    """Summarize shadow reviews, category dismissal rates, and approvals after blocks."""
    typer.echo(json.dumps(build_shadow_report(), sort_keys=True, default=str))


def _run_id_from_diff(diff_file: Path) -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


async def _invoke_review_graph(
    state: dict[str, Any],
    database_path: str,
    thread_id: str,
    clients: dict[str, ScriptedLLM] | None = None,
) -> dict[str, Any]:
    """Run the review graph with the async SQLite checkpoint saver."""
    async with AsyncSqliteSaver.from_conn_string(database_path) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer=checkpointer, clients=clients)
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


def parse_pull_request_target(target: str) -> tuple[str, str, int]:
    """Parse owner/repository#number from the review-pr argument."""
    owner_repo, separator, number_text = target.partition("#")
    owner, slash, repo = owner_repo.partition("/")
    if not separator or not slash or not owner or not repo or not number_text.isdigit():
        raise ValueError("Pull request must use owner/repo#number format.")
    return owner, repo, int(number_text)


def review_pull_request(
    target: str,
    *,
    github_client: Any | None = None,
    clients: dict[str, ScriptedLLM] | None = None,
    publish: bool = True,
) -> dict[str, Any]:
    """Fetch a PR, invoke the review graph, and publish status and report comment."""
    owner, repo, number = parse_pull_request_target(target)
    api = github_client or GitHubClient()
    owns_client = github_client is None
    pr: PullRequest | None = None
    run_id: str | None = None
    try:
        pr = api.get_pull_request(owner, repo, number)
        try:
            ci_status = api.read_ci_status(owner, repo, pr.head_sha)
            external_incomplete = False
        except (GitHubAPIError, httpx.HTTPError):
            ci_status = "missing"
            external_incomplete = True
        run_id = _run_id_from_diff(Path(f"{owner}-{repo}-{number}.diff"))
        insert_run(
            run_id,
            repo=pr.repo,
            pr_number=number,
            head_sha=pr.head_sha,
            status="running",
            outcome="pending",
        )
        checkpoint_connection = connect()
        database_path = str(checkpoint_connection.execute("PRAGMA database_list").fetchone()[2])
        checkpoint_connection.close()
        result = asyncio.run(
            _invoke_review_graph(
                {
                    "pr": pr,
                    "repo_path": str(Path.cwd()),
                    "run_id": run_id,
                    "ci_status": ci_status,
                    "incomplete": external_incomplete,
                },
                database_path,
                f"{pr.repo}#{number}@{pr.head_sha}",
                clients=clients,
            )
        )
        decision = cast(Decision, result["decision"])
        findings = cast(list[Finding], result.get("decision_findings", []))
        verified = cast(list[Finding], result.get("verified_findings", []))
        for finding in verified:
            status = "shown" if finding in findings else "dismissed"
            insert_finding(run_id, {**finding.model_dump(), "verified": True, "status": status})
        report = str(
            result.get("report")
            or reporter.run({"findings": findings, "decision": decision})["report"]
        )
        status_payload = None
        comment = None
        if publish:
            status_payload = api.set_commit_status(
                owner,
                repo,
                pr.head_sha,
                decision.outcome,
                decision.reasons[0] if decision.reasons else f"MergeGuard: {decision.outcome}",
            )
            comment = api.post_or_update_comment(owner, repo, number, report)
        record(
            run_id,
            "github",
            "published",
            {
                "outcome": decision.outcome,
                "status": status_payload.get("state") if status_payload else "shadow",
                "comment_id": comment.get("id") if comment else None,
            },
        )
        insert_run(
            run_id,
            repo=pr.repo,
            pr_number=number,
            head_sha=pr.head_sha,
            finished_at="now",
            status="waiting" if result.get("__interrupt__") else "finished",
            outcome=decision.outcome,
        )
        return {"run_id": run_id, "decision": decision, "report": report, "status": status_payload}
    except (GitHubAPIError, httpx.HTTPError):
        return _incomplete_review_result(
            "GitHub API access failed during review.",
            head_sha=pr.head_sha if pr else "",
            run_id=run_id,
        )
    except sqlite3.Error:
        return _incomplete_review_result(
            "Review checkpoint storage is unavailable.",
            head_sha=pr.head_sha if pr else "",
            run_id=run_id,
        )
    finally:
        if owns_client:
            api.close()


def _incomplete_review_result(
    reason: str, *, head_sha: str = "", run_id: str | None = None
) -> dict[str, Any]:
    """Return a safe needs_human result when an external prerequisite is unavailable."""
    decision = Decision(
        outcome="needs_human",
        reasons=[reason],
        head_sha=head_sha,
        risk_score=0,
        complete=False,
    )
    report = reporter.run({"findings": [], "decision": decision})["report"]
    return {
        "run_id": run_id or "unavailable",
        "decision": decision,
        "report": report,
        "status": None,
    }


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


def watch_repository_once(
    target: str,
    *,
    github_client: Any,
    shadow: bool = False,
    clients: dict[str, ScriptedLLM] | None = None,
) -> list[dict[str, Any]]:
    """Poll open PRs once, processing new heads once and resuming waiting reviews."""
    owner, slash, repo = target.partition("/")
    if not slash or not owner or not repo or "#" in repo:
        raise ValueError("Repository must use owner/repo format.")
    actions: list[dict[str, Any]] = []
    for item in github_client.list_open_pull_requests(owner, repo):
        number = int(item["number"])
        head_sha = str(item.get("head", {}).get("sha", ""))
        if not head_sha:
            continue
        repository = f"{owner}/{repo}"
        existing = find_review_run(repository, number, head_sha)
        if existing is None:
            result = review_pull_request(
                f"{repository}#{number}",
                github_client=github_client,
                clients=clients,
                publish=not shadow,
            )
            actions.append(
                {"pr": number, "action": "reviewed", "outcome": result["decision"].outcome}
            )
            continue
        if existing.get("status") != "waiting":
            actions.append(
                {"pr": number, "action": "already_processed", "run_id": existing["run_id"]}
            )
            continue
        if shadow:
            actions.append({"pr": number, "action": "waiting_shadow", "run_id": existing["run_id"]})
            continue
        resumed = _resume_waiting_review(
            existing["run_id"], github_client, owner, repo, number, clients
        )
        actions.append(
            {
                "pr": number,
                "action": "resumed" if resumed else "waiting",
                "run_id": existing["run_id"],
            }
        )
    return actions


def _resume_waiting_review(
    run_id: str,
    github_client: Any,
    owner: str,
    repo: str,
    number: int,
    clients: dict[str, ScriptedLLM] | None,
) -> bool:
    """Find an approver command and resume the matching saved graph checkpoint."""
    run = get_run(run_id)
    if run is None:
        return False
    thread_id = f"{run['repo']}#{number}@{run['head_sha']}"
    database = connect()
    database_path = str(database.execute("PRAGMA database_list").fetchone()[2])
    database.close()

    async def resume_comment(comment_text: str, by_user: str) -> dict[str, Any]:
        async with AsyncSqliteSaver.from_conn_string(database_path) as saver:
            await saver.setup()
            graph = build_graph(checkpointer=saver, clients=clients)
            return await human_gate.resume_review(graph, thread_id, comment_text, by_user)

    comments = github_client.list_issue_comments(owner, repo, number)
    for comment in reversed(comments):
        user = str(comment.get("user", {}).get("login", ""))
        body = str(comment.get("body", ""))
        for line in reversed(body.splitlines()):
            if not line.strip().lower().startswith("/mergeguard "):
                continue
            try:
                result = asyncio.run(resume_comment(line.strip(), user))
            except human_gate.ApprovalRejected:
                continue
            decision = cast(Decision, result["decision"])
            report = str(
                result.get("report")
                or reporter.run(
                    {"findings": result.get("decision_findings", []), "decision": decision}
                )["report"]
            )
            status = github_client.set_commit_status(
                owner,
                repo,
                str(run["head_sha"]),
                decision.outcome,
                decision.reasons[0] if decision.reasons else f"MergeGuard: {decision.outcome}",
            )
            github_client.post_or_update_comment(owner, repo, number, report)
            record(
                run_id,
                "github",
                "published",
                {"outcome": decision.outcome, "status": status.get("state")},
            )
            insert_run(
                run_id,
                repo=run["repo"],
                pr_number=number,
                head_sha=run["head_sha"],
                finished_at="now",
                status="waiting" if result.get("__interrupt__") else "finished",
                outcome=decision.outcome,
            )
            return True
    return False


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
