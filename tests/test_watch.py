# Exercises polling idempotency, shadow behavior and comment-driven checkpoint resume.

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from mergeguard import storage
from mergeguard.cli import watch_repository_once
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import PullRequest
from mergeguard.settings import settings

DIFF = """diff --git a/src/sample.py b/src/sample.py
--- a/src/sample.py
+++ b/src/sample.py
@@ -1 +1 @@
+value = 1
"""


class WatchGitHub:
    def __init__(self, ci_status: str = "passing", head_sha: str = "head-7") -> None:
        self.ci_status = ci_status
        self.head_sha = head_sha
        self.comments: list[dict[str, Any]] = []
        self.statuses: list[str] = []
        self.published_comments: list[str] = []
        self.pull_fetches = 0

    def list_open_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        assert (owner, repo) == ("acme", "widget")
        return [{"number": 7, "head": {"sha": self.head_sha}}]

    def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        self.pull_fetches += 1
        return PullRequest(
            repo=f"{owner}/{repo}",
            number=number,
            head_sha=self.head_sha,
            base_sha="base",
            title="Add sample",
            body="",
            author="author",
            diff=DIFF,
            files=["src/sample.py"],
        )

    def read_ci_status(self, owner: str, repo: str, sha: str) -> str:
        del owner, repo, sha
        return self.ci_status

    def set_commit_status(self, owner: str, repo: str, sha: str, outcome: str, description: str):
        del owner, repo, sha, description
        self.statuses.append(outcome)
        return {"state": outcome}

    def post_or_update_comment(self, owner: str, repo: str, number: int, body: str):
        del owner, repo, number
        self.published_comments.append(body)
        return {"id": 1}

    def list_issue_comments(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        del owner, repo, number
        return list(self.comments)


def _clients() -> dict[str, ScriptedLLM]:
    return {
        "security_reviewer": ScriptedLLM([[]]),
        "correctness_reviewer": ScriptedLLM([[]]),
        "test_reviewer": ScriptedLLM([[]]),
        "skeptic": ScriptedLLM([]),
    }


def test_watch_processes_each_head_once_and_shadow_does_not_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(storage, "DATABASE_PATH", str(tmp_path / "watch-shadow.db"))
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    monkeypatch.chdir(tmp_path)
    github = WatchGitHub()

    first = watch_repository_once(
        "acme/widget", github_client=github, shadow=True, clients=_clients()
    )
    second = watch_repository_once(
        "acme/widget", github_client=github, shadow=True, clients=_clients()
    )
    github.head_sha = "head-8"
    third = watch_repository_once(
        "acme/widget", github_client=github, shadow=True, clients=_clients()
    )

    assert first[0]["action"] == "reviewed"
    assert second[0]["action"] == "already_processed"
    assert third[0]["action"] == "reviewed"
    assert github.pull_fetches == 2
    assert github.statuses == []
    assert github.published_comments == []


def test_watch_resumes_waiting_head_from_approver_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(storage, "DATABASE_PATH", str(tmp_path / "watch-resume.db"))
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".mergeguard.yml").write_text(
        yaml.safe_dump({"approvers": ["reviewer"]}), encoding="utf-8"
    )
    github = WatchGitHub(ci_status="missing")

    initial = watch_repository_once("acme/widget", github_client=github, clients=_clients())
    github.comments.append({"user": {"login": "reviewer"}, "body": "/mergeguard approve"})
    resumed = watch_repository_once("acme/widget", github_client=github, clients=_clients())

    assert initial[0]["action"] == "reviewed"
    assert resumed[0]["action"] == "resumed"
    assert github.statuses == ["needs_human", "pass"]
    assert len(github.published_comments) == 2
    run = storage.find_review_run("acme/widget", 7, "head-7")
    assert run is not None and run["status"] == "finished" and run["outcome"] == "pass"
