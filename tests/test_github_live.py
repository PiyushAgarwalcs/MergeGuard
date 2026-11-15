from __future__ import annotations

import pytest

from mergeguard.github import GitHubClient
from mergeguard.settings import settings

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not settings.MERGEGUARD_GITHUB_TOKEN or not settings.TEST_REPO,
    reason="MERGEGUARD_GITHUB_TOKEN and TEST_REPO are required for the read-only live check",
)
def test_live_github_client_lists_configured_repository_prs() -> None:
    """Exercise an authenticated read-only request against the configured test repository."""
    owner, separator, repo = settings.TEST_REPO.partition("/")
    assert separator and owner and repo, "TEST_REPO must use owner/repo format"
    with GitHubClient() as client:
        pull_requests = client.list_open_pull_requests(owner, repo)
    assert isinstance(pull_requests, list)
