# mergeguard.api
# Exposes the FastAPI application and health endpoint for the review service.
# Webhook authentication is a separate helper so its trust checks stay testable.

import hashlib
import hmac
import json
import sqlite3
from collections.abc import Callable
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from mergeguard.github import GitHubClient
from mergeguard.settings import settings
from mergeguard.storage import find_review_run, insert_delivery

app = FastAPI(title="MergeGuard")
WEBHOOK_HANDLER: Callable[[str, dict[str, Any]], None] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def verify_webhook_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify a GitHub-style sha256 signature using constant-time comparison."""
    if not signature or not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def accept_webhook_delivery(
    body: bytes,
    signature: str | None,
    secret: str,
    delivery_id: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> bool:
    """Accept a valid, first-seen webhook delivery and reject replays."""
    if not verify_webhook_signature(body, signature, secret):
        return False
    result = insert_delivery(delivery_id, connection=connection)
    return bool(result["inserted"])


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    """Authenticate a GitHub delivery, deduplicate it and schedule supported events."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    secret = settings.MERGEGUARD_WEBHOOK_SECRET
    if not secret or not verify_webhook_signature(body, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")
    event = request.headers.get("X-GitHub-Event", "")
    if event not in {"pull_request", "issue_comment"}:
        return {"accepted": False, "ignored": True}
    delivery_id = request.headers.get("X-GitHub-Delivery", "").strip()
    if not delivery_id:
        raise HTTPException(status_code=400, detail="Missing GitHub delivery id.")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail="Webhook body must be valid JSON.") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object.")
    if not accept_webhook_delivery(body, signature, secret, delivery_id):
        return {"accepted": False, "duplicate": True}
    background_tasks.add_task(_dispatch_webhook, event, payload)
    return {"accepted": True, "delivery_id": delivery_id}


def _dispatch_webhook(event: str, payload: dict[str, Any]) -> None:
    """Invoke the configured processor or the built-in GitHub event dispatcher."""
    if WEBHOOK_HANDLER is not None:
        WEBHOOK_HANDLER(event, payload)
        return
    process_webhook_event(event, payload)


def process_webhook_event(event: str, payload: dict[str, Any]) -> None:
    """Route supported pull request and approver-comment events to the review service."""
    repository = payload.get("repository")
    if not isinstance(repository, dict):
        return
    full_name = str(repository.get("full_name", ""))
    if full_name.count("/") != 1:
        return
    number = payload.get("number")
    issue = payload.get("issue")
    if event == "issue_comment" and isinstance(issue, dict):
        if not issue.get("pull_request") or payload.get("action") != "created":
            return
        number = issue.get("number")
    elif event == "pull_request" and payload.get("action") not in {
        "opened",
        "reopened",
        "synchronize",
    }:
        return
    if number is None:
        return
    try:
        pull_number = int(number)
    except (TypeError, ValueError):
        return
    if event == "pull_request":
        from mergeguard.cli import review_pull_request

        review_pull_request(f"{full_name}#{pull_number}")
        return
    owner, repo = full_name.split("/", maxsplit=1)
    with GitHubClient() as client:
        pull_request = client.get_pull_request(owner, repo, pull_number)
        run = find_review_run(full_name, pull_number, pull_request.head_sha)
        if run is None or run.get("status") != "waiting":
            return
        from mergeguard.cli import _resume_waiting_review

        _resume_waiting_review(run["run_id"], client, owner, repo, pull_number, None)
