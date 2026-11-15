# Tests the review-pr orchestration with a fixture PR and a stub publication client.

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mergeguard import storage
from mergeguard.cli import app, parse_pull_request_target, review_pull_request
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import PullRequest
from mergeguard.settings import settings

DIFF = """diff --git a/src/sample.py b/src/sample.py
--- a/src/sample.py
+++ b/src/sample.py
@@ -1 +1 @@
+value = 1
"""


class FakeGitHub:
    def __init__(self, ci_status: str = "passing") -> None:
        self.ci_status = ci_status
        self.statuses: list[dict[str, Any]] = []
        self.comments: list[str] = []

    def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        assert (owner, repo, number) == ("acme", "widget", 7)
        return PullRequest(
            repo="acme/widget",
            number=7,
            head_sha="head-7",
            base_sha="base-7",
            title="Add sample",
            body="",
            author="author",
            diff=DIFF,
            files=["src/sample.py"],
        )

    def read_ci_status(self, owner: str, repo: str, sha: str) -> str:
        assert (owner, repo, sha) == ("acme", "widget", "head-7")
        return self.ci_status

    def set_commit_status(self, owner: str, repo: str, sha: str, outcome: str, description: str):
        status = {"pass": "success", "needs_human": "pending", "block": "failure"}[outcome]
        payload = {"state": status, "outcome": outcome, "description": description}
        self.statuses.append(payload)
        return payload

    def post_or_update_comment(self, owner: str, repo: str, number: int, body: str):
        self.comments.append(body)
        return {"id": 101, "body": body}


def _clients() -> dict[str, ScriptedLLM]:
    return {
        "security_reviewer": ScriptedLLM([[]]),
        "correctness_reviewer": ScriptedLLM([[]]),
        "test_reviewer": ScriptedLLM([[]]),
        "skeptic": ScriptedLLM([]),
    }


def test_pull_request_target_parser() -> None:
    assert parse_pull_request_target("acme/widget#7") == ("acme", "widget", 7)
    with pytest.raises(ValueError, match="owner/repo#number"):
        parse_pull_request_target("widget/7")


@pytest.mark.parametrize(
    ("ci_status", "expected_outcome", "expected_status"),
    [("passing", "pass", "success"), ("missing", "needs_human", "pending")],
)
def test_review_pull_request_publishes_graph_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ci_status: str,
    expected_outcome: str,
    expected_status: str,
) -> None:
    database = tmp_path / "review-pr.db"
    monkeypatch.setattr(storage, "DATABASE_PATH", str(database))
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    github = FakeGitHub(ci_status)

    result = review_pull_request("acme/widget#7", github_client=github, clients=_clients())

    assert result["decision"].outcome == expected_outcome
    assert github.statuses[0]["state"] == expected_status
    assert len(github.comments) == 1
    assert github.comments[0].startswith("## MergeGuard review")


def test_review_pr_cli_rejects_invalid_target() -> None:
    result = CliRunner().invoke(app, ["review-pr", "not-a-pull-request"])

    assert result.exit_code == 1
    assert "owner/repo#number" in result.output
