# mergeguard.watch_service
# Polls repositories and resumes checkpointed reviews for waiting PRs.

from __future__ import annotations

import asyncio
from typing import Any, cast

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from mergeguard.agents import reporter
from mergeguard.checks import human_gate
from mergeguard.graph import build_graph
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import Decision
from mergeguard.review_service import review_pull_request
from mergeguard.storage import connect, find_review_run, get_run, insert_run
from mergeguard.tracing import record


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
