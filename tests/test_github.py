# Exercises GitHub API behavior with recorded responses and an in-process transport.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from mergeguard.github import COMMENT_MARKER, GitHubAPIError, GitHubClient

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "github"


def _fixture(name: str) -> Any:
    if name.endswith(".diff"):
        return (FIXTURES / name).read_text(encoding="utf-8")
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _fixture_transport(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/pulls/7") and request.headers.get("Accept") == "application/vnd.github.diff":
        return httpx.Response(200, text=_fixture("review.diff"))
    if path.endswith("/pulls/7"):
        return httpx.Response(200, json=_fixture("pull_request.json"))
    if path.endswith("/pulls/7/files"):
        return httpx.Response(200, json=_fixture("changed_files.json"))
    if path.endswith("/commits/0123456789abcdef0123456789abcdef01234567/status"):
        return httpx.Response(200, json=_fixture("combined_status.json"))
    if path.endswith("/commits/0123456789abcdef0123456789abcdef01234567/check-runs"):
        return httpx.Response(200, json=_fixture("check_runs.json"))
    if path.endswith("/issues/7/comments"):
        return httpx.Response(200, json=_fixture("comments.json"))
    if path.endswith("/issues/comments/42"):
        return httpx.Response(200, json={"id": 42, "body": json.loads(request.content)["body"]})
    if path.endswith("/statuses/0123456789abcdef0123456789abcdef01234567"):
        return httpx.Response(201, json=json.loads(request.content))
    if path.endswith("/pulls"):
        return httpx.Response(200, json=_fixture("open_pull_requests.json"))
    return httpx.Response(404, json={"message": "fixture not found"})


def test_github_client_reads_pr_ci_and_updates_single_comment() -> None:
    with GitHubClient(
        token="",
        base_url="https://fixture.invalid",
        transport=httpx.MockTransport(_fixture_transport),
    ) as client:
        pr = client.get_pull_request("acme", "widget", 7)
        assert pr.repo == "acme/widget"
        assert pr.head_sha.startswith("012345")
        assert pr.files == ["src/report.py"]
        assert "value = 2" in pr.diff
        assert client.read_ci_status("acme", "widget", pr.head_sha) == "passing"

        comment = client.post_or_update_comment("acme", "widget", 7, "Review result")
        assert comment["id"] == 42
        assert COMMENT_MARKER in comment["body"]
        status = client.set_commit_status(
            "acme", "widget", pr.head_sha, "needs_human", "Review needed"
        )
        assert status["state"] == "pending"
        assert status["context"] == "mergeguard"
        assert len(client.list_open_pull_requests("acme", "widget")) == 1


def test_github_client_retries_server_errors_and_rate_limits() -> None:
    responses = iter(
        [
            httpx.Response(503, headers={"Retry-After": "0"}),
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=[]),
        ]
    )
    waits: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return next(responses)

    with GitHubClient(
        token="",
        base_url="https://fixture.invalid",
        transport=httpx.MockTransport(handler),
        sleep=waits.append,
    ) as client:
        assert client.list_open_pull_requests("acme", "widget") == []
    assert waits == [0.0, 0.0]


def test_github_client_paginates_and_reports_exhausted_retries() -> None:
    calls: list[int] = []

    def pages(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        calls.append(page)
        return httpx.Response(
            200,
            json=[{"filename": f"file-{index}.py"} for index in range(100)] if page == 1 else [],
        )

    with GitHubClient(
        token="", base_url="https://fixture.invalid", transport=httpx.MockTransport(pages)
    ) as client:
        assert len(client.list_changed_files("acme", "widget", 7)) == 100
    assert calls == [1, 2]

    def unavailable(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(503)

    with (
        GitHubClient(
            token="",
            base_url="https://fixture.invalid",
            transport=httpx.MockTransport(unavailable),
            sleep=lambda _: None,
            max_attempts=2,
        ) as client,
        pytest.raises(GitHubAPIError, match="2 attempts"),
    ):
        client.list_open_pull_requests("acme", "widget")
