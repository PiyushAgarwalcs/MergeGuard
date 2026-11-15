# Centralizes GitHub API access so review agents never receive network credentials.

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Self

import httpx

from mergeguard.models import PullRequest
from mergeguard.settings import settings

API_URL = "https://api.github.com"
COMMENT_MARKER = "<!-- mergeguard -->"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3


class GitHubAPIError(RuntimeError):
    """An API request failed after applying the configured retry policy."""


class GitHubClient:
    """Small synchronous GitHub REST client with injectable transport and clock."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = API_URL,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive.")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "MergeGuard",
        }
        credential = settings.MERGEGUARD_GITHUB_TOKEN if token is None else token
        if credential:
            headers["Authorization"] = f"Bearer {credential}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, transport=transport, timeout=20.0
        )
        self._sleep = sleep
        self._max_attempts = max_attempts

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_pull_request_payload(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        """Fetch the raw GitHub pull request payload."""
        return self._json("GET", f"/repos/{owner}/{repo}/pulls/{number}")

    def get_pull_request_diff(self, owner: str, repo: str, number: int) -> str:
        """Fetch the unified diff for one pull request."""
        response = self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{number}",
            headers={"Accept": "application/vnd.github.diff"},
        )
        return response.text

    def list_changed_files(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        """Fetch every changed file, following the API's 100-file page size."""
        path = f"/repos/{owner}/{repo}/pulls/{number}/files"
        return self._pages(path)

    def read_ci_status(self, owner: str, repo: str, sha: str) -> str:
        """Combine commit status and check runs into passing, failing, or missing."""
        combined = self._json("GET", f"/repos/{owner}/{repo}/commits/{sha}/status")
        checks = self._json("GET", f"/repos/{owner}/{repo}/commits/{sha}/check-runs")
        states = [str(item.get("state", "")) for item in combined.get("statuses", [])]
        runs = checks.get("check_runs", [])
        if not states and not runs:
            return "missing"
        if "failure" in states or "error" in states:
            return "failing"
        if any(
            item.get("status") == "completed"
            and item.get("conclusion") not in {"success", "neutral", "skipped"}
            for item in runs
        ):
            return "failing"
        if "pending" in states or any(item.get("status") != "completed" for item in runs):
            return "missing"
        return "passing"

    def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        """Fetch PR metadata, its diff and changed files into the shared contract."""
        payload = self.get_pull_request_payload(owner, repo, number)
        files = self.list_changed_files(owner, repo, number)
        diff = self.get_pull_request_diff(owner, repo, number)
        return PullRequest(
            repo=f"{owner}/{repo}",
            number=number,
            head_sha=str(payload["head"]["sha"]),
            base_sha=str(payload["base"]["sha"]),
            title=str(payload.get("title", "")),
            body=str(payload.get("body") or ""),
            author=str(payload.get("user", {}).get("login", "unknown")),
            diff=diff,
            files=[str(item["filename"]) for item in files],
        )

    def post_or_update_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        """Create or update the one bot comment identified by its hidden marker."""
        comments = self._pages(f"/repos/{owner}/{repo}/issues/{issue_number}/comments")
        marked_body = body if COMMENT_MARKER in body else f"{COMMENT_MARKER}\n{body}"
        existing = next(
            (item for item in comments if COMMENT_MARKER in str(item.get("body", ""))), None
        )
        if existing is not None:
            return self._json(
                "PATCH",
                f"/repos/{owner}/{repo}/issues/comments/{existing['id']}",
                json={"body": marked_body},
            )
        return self._json(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": marked_body},
        )

    def set_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        outcome: str,
        description: str,
        target_url: str | None = None,
    ) -> dict[str, Any]:
        """Publish the MergeGuard status using the documented decision mapping."""
        state = {"pass": "success", "needs_human": "pending", "block": "failure"}.get(outcome)
        if state is None:
            raise ValueError(f"Unknown MergeGuard outcome {outcome!r}.")
        payload: dict[str, Any] = {
            "state": state,
            "context": "mergeguard",
            "description": description[:140],
        }
        if target_url:
            payload["target_url"] = target_url
        return self._json("POST", f"/repos/{owner}/{repo}/statuses/{sha}", json=payload)

    def list_issue_comments(self, owner: str, repo: str, issue_number: int) -> list[dict[str, Any]]:
        """List all comments for a pull request or issue."""
        return self._pages(f"/repos/{owner}/{repo}/issues/{issue_number}/comments")

    def list_open_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """List every open pull request in a repository."""
        return self._pages(f"/repos/{owner}/{repo}/pulls", params={"state": "open"})

    def _pages(self, path: str, *, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self._request(
                "GET", path, params={**(params or {}), "per_page": "100", "page": str(page)}
            )
            payload = response.json()
            if not isinstance(payload, list):
                raise GitHubAPIError(f"Expected a list from {path}.")
            results.extend(item for item in payload if isinstance(item, dict))
            if len(payload) < 100:
                return results
            page += 1

    def _json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._request(method, path, **kwargs)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GitHubAPIError(f"Expected an object from {path}.")
        return payload

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self._max_attempts):
            response = self._client.request(method, path, **kwargs)
            if not self._is_retryable(response):
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as error:
                    raise GitHubAPIError(
                        f"GitHub API returned HTTP {response.status_code} for {path}."
                    ) from error
                return response
            if attempt + 1 == self._max_attempts:
                raise GitHubAPIError(
                    f"GitHub API remained unavailable after {self._max_attempts} attempts."
                )
            self._sleep(self._retry_delay(response, attempt))
        raise GitHubAPIError("GitHub API retry policy ended unexpectedly.")

    @staticmethod
    def _is_retryable(response: httpx.Response) -> bool:
        if response.status_code in RETRYABLE_STATUS:
            return True
        return response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(60.0, max(0.0, float(retry_after)))
            except ValueError:
                try:
                    retry_at = datetime.strptime(retry_after, "%a, %d %b %Y %H:%M:%S GMT")
                    return float(
                        min(
                            60.0,
                            max(
                                0.0,
                                (retry_at - datetime.now(UTC).replace(tzinfo=None)).total_seconds(),
                            ),
                        )
                    )
                except ValueError:
                    pass
        return float(min(8.0, 0.5 * float(2**attempt)))


__all__ = ["COMMENT_MARKER", "GitHubAPIError", "GitHubClient"]
