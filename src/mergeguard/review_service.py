# mergeguard.review_service
# Implements local and GitHub review execution and checkpoint resume.

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from pathlib import Path
from typing import Any, cast

import httpx
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from mergeguard.agents import reporter
from mergeguard.github import GitHubAPIError, GitHubClient
from mergeguard.graph import build_graph
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import Decision, Finding, PullRequest
from mergeguard.storage import (
    connect,
    insert_finding,
    insert_run,
)
from mergeguard.tracing import record


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
