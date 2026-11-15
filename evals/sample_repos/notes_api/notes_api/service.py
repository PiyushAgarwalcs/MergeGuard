# Business logic for the sample notes service.
# Validation stays separate from persistence and transport handling.

from notes_api import db
from notes_api.auth import require_user


def create_note(database_path: str, user_id: str | None, title: str, body: str) -> int:
    """Validate and create a user's note."""
    owner = require_user(user_id)
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("A title is required.")
    if len(clean_title) > 120:
        raise ValueError("The title must be at most 120 characters.")
    if len(body) > 20_000:
        raise ValueError("The body must be at most 20000 characters.")
    return db.insert_note(database_path, owner, clean_title, body)


def get_note(database_path: str, user_id: str | None, note_id: int) -> dict | None:
    """Return a note owned by the authenticated user."""
    owner = require_user(user_id)
    if note_id < 1:
        raise ValueError("Note ids must be positive.")
    return db.select_note(database_path, owner, note_id)


def list_notes(database_path: str, user_id: str | None) -> list[dict]:
    """Return all notes owned by the authenticated user."""
    return db.select_notes(database_path, require_user(user_id))


def search_notes(database_path: str, user_id: str | None, term: str, limit: int = 20) -> list[dict]:
    """Search a user's notes with a bounded result count."""
    owner = require_user(user_id)
    if limit < 1 or limit > 100:
        raise ValueError("Search limit must be between 1 and 100.")
    if not term.strip():
        return []
    return db.search_notes(database_path, owner, term.strip(), limit)


def update_note(
    database_path: str,
    user_id: str | None,
    note_id: int,
    title: str,
    body: str,
) -> bool:
    """Validate and update a note owned by the authenticated user."""
    owner = require_user(user_id)
    clean_title = title.strip()
    if note_id < 1:
        raise ValueError("Note ids must be positive.")
    if not clean_title:
        raise ValueError("A title is required.")
    if len(clean_title) > 120 or len(body) > 20_000:
        raise ValueError("The note exceeds its allowed length.")
    return db.update_note(database_path, owner, note_id, clean_title, body)


def remove_note(database_path: str, user_id: str | None, note_id: int) -> bool:
    """Delete a note owned by the authenticated user."""
    owner = require_user(user_id)
    if note_id < 1:
        raise ValueError("Note ids must be positive.")
    return db.delete_note(database_path, owner, note_id)
