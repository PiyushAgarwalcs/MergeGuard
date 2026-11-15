# Transport-neutral handlers for the URL-shortener service.
# Authentication is checked before owner-scoped operations run.

import hmac
import logging

from shortener.service import delete_link, link_stats, list_links, resolve, shorten

LOGGER = logging.getLogger(__name__)


class ShortenerApi:
    """Small API facade suitable for a web adapter or tests."""

    def __init__(self, database_path: str, api_token: str) -> None:
        """Store API configuration."""
        self.database_path = database_path
        self.api_token = api_token

    def _check(self, token: str, owner: str) -> str:
        """Verify request credentials and return an owner identity."""
        if not self.api_token or not hmac.compare_digest(token, self.api_token):
            LOGGER.warning("Rejected shortener request with invalid credentials.")
            raise PermissionError("Invalid API token.")
        if not owner.strip():
            raise PermissionError("An owner is required.")
        return owner

    def create(self, token: str, owner: str, destination: str) -> str:
        """Create a shortened URL for the authenticated owner."""
        return shorten(self.database_path, destination, self._check(token, owner))

    def redirect_target(self, code: str) -> str | None:
        """Resolve a public short code."""
        return resolve(self.database_path, code)

    def list(self, token: str, owner: str) -> list[dict[str, object]]:
        """List mappings belonging to the authenticated owner."""
        return list_links(self.database_path, self._check(token, owner))

    def stats(self, token: str, owner: str) -> dict[str, int]:
        """Return aggregate counts for the authenticated owner."""
        return link_stats(self.database_path, self._check(token, owner))

    def delete(self, token: str, owner: str, code: str) -> bool:
        """Delete a mapping belonging to the authenticated owner."""
        return delete_link(self.database_path, code, self._check(token, owner))
