# Transport-neutral API handlers for the sample notes service.
# The handlers enforce the token before accepting a user identity.

from __future__ import annotations

import logging

from notes_api.auth import is_authorized
from notes_api.service import (
    create_note,
    get_note,
    list_notes,
    remove_note,
    search_notes,
    update_note,
)

LOGGER = logging.getLogger(__name__)


class NotesApi:
    """Small API facade used by a web adapter or tests."""

    def __init__(self, database_path: str, api_token: str) -> None:
        """Store the configured database and API token."""
        self.database_path = database_path
        self.api_token = api_token

    def _user(self, token: str, user_id: str) -> str:
        """Validate the API token and return the user identity."""
        if not is_authorized(token, self.api_token):
            LOGGER.warning("Rejected notes API request with invalid credentials.")
            raise PermissionError("Invalid API token.")
        return user_id

    def create(self, token: str, user_id: str, title: str, body: str) -> int:
        """Create a note after authenticating the request."""
        return create_note(self.database_path, self._user(token, user_id), title, body)

    def get(self, token: str, user_id: str, note_id: int) -> dict | None:
        """Fetch a note after authenticating the request."""
        return get_note(self.database_path, self._user(token, user_id), note_id)

    def list(self, token: str, user_id: str) -> list[dict]:
        """List notes after authenticating the request."""
        return list_notes(self.database_path, self._user(token, user_id))

    def search(self, token: str, user_id: str, term: str, limit: int = 20) -> list[dict]:
        """Search the authenticated user's notes."""
        return search_notes(self.database_path, self._user(token, user_id), term, limit)

    def update(self, token: str, user_id: str, note_id: int, title: str, body: str) -> bool:
        """Update a note after authenticating the request."""
        return update_note(
            self.database_path,
            self._user(token, user_id),
            note_id,
            title,
            body,
        )

    def delete(self, token: str, user_id: str, note_id: int) -> bool:
        """Delete a note after authenticating the request."""
        return remove_note(self.database_path, self._user(token, user_id), note_id)
