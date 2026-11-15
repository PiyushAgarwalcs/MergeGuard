# Examples of notes service behavior and authorization boundaries.
# Temporary databases keep tests isolated and repeatable.

import pytest
from notes_api.api import NotesApi
from notes_api.db import initialize


@pytest.fixture
def api(tmp_path) -> NotesApi:
    """Provide an initialized API backed by a temporary database."""
    database_path = str(tmp_path / "notes.sqlite")
    initialize(database_path)
    return NotesApi(database_path, "test-token")


def test_create_and_list_notes_for_owner(api: NotesApi) -> None:
    """A user can create and list their own notes."""
    note_id = api.create("test-token", "alice", "  Trip  ", "Pack a map.")

    notes = api.list("test-token", "alice")

    assert notes[0]["id"] == note_id
    assert notes[0]["title"] == "Trip"


def test_user_cannot_read_or_delete_another_users_note(api: NotesApi) -> None:
    """Note ownership is applied to reads and deletes."""
    note_id = api.create("test-token", "alice", "Private", "Text.")

    assert api.get("test-token", "bob", note_id) is None
    assert not api.delete("test-token", "bob", note_id)
    assert api.get("test-token", "alice", note_id) is not None


def test_invalid_token_is_rejected(api: NotesApi) -> None:
    """API operations require the configured token."""
    with pytest.raises(PermissionError):
        api.list("wrong-token", "alice")


def test_blank_title_is_rejected(api: NotesApi) -> None:
    """The service rejects a title that becomes blank after trimming."""
    with pytest.raises(ValueError, match="title"):
        api.create("test-token", "alice", "  ", "Text.")


def test_search_treats_wildcards_as_literal_text(api: NotesApi) -> None:
    """Search input cannot broaden a query using SQL pattern characters."""
    api.create("test-token", "alice", "100% complete", "A literal percent.")
    api.create("test-token", "alice", "1000 complete", "A different title.")

    matches = api.search("test-token", "alice", "%")

    assert [note["title"] for note in matches] == ["100% complete"]


def test_search_is_scoped_to_user_and_has_a_bounded_limit(api: NotesApi) -> None:
    """Search results are private and oversized limits are refused."""
    api.create("test-token", "alice", "Shared word", "Private.")
    api.create("test-token", "bob", "Shared word", "Other.")

    assert len(api.search("test-token", "alice", "Shared")) == 1
    with pytest.raises(ValueError, match="limit"):
        api.search("test-token", "alice", "Shared", 101)


def test_update_note_is_owner_scoped(api: NotesApi) -> None:
    """A user can edit their own note but cannot edit another user's note."""
    note_id = api.create("test-token", "alice", "First", "Before.")

    assert not api.update("test-token", "bob", note_id, "Changed", "No.")
    assert api.update("test-token", "alice", note_id, "Changed", "After.")
    assert api.get("test-token", "alice", note_id)["body"] == "After."


def test_search_with_blank_term_returns_no_results(api: NotesApi) -> None:
    """Blank search text does not return every private note."""
    api.create("test-token", "alice", "Anything", "Text.")

    assert api.search("test-token", "alice", "   ") == []


def test_update_rejects_blank_title(api: NotesApi) -> None:
    """Updates preserve the required non-empty title invariant."""
    note_id = api.create("test-token", "alice", "Title", "Text.")

    with pytest.raises(ValueError, match="title"):
        api.update("test-token", "alice", note_id, " ", "Updated.")


def test_owner_can_delete_note(api: NotesApi) -> None:
    """A note disappears from its owner's list after deletion."""
    note_id = api.create("test-token", "alice", "Temporary", "Text.")

    assert api.delete("test-token", "alice", note_id)
    assert api.list("test-token", "alice") == []


def test_note_length_limits_apply_before_persistence(api: NotesApi) -> None:
    """Oversized values are rejected and do not create a partial note."""
    with pytest.raises(ValueError, match="120 characters"):
        api.create("test-token", "alice", "x" * 121, "Text.")
    with pytest.raises(ValueError, match="20000 characters"):
        api.create("test-token", "alice", "Title", "x" * 20_001)

    assert api.list("test-token", "alice") == []


def test_search_limit_can_return_a_small_page(api: NotesApi) -> None:
    """A caller can request a smaller bounded search result."""
    api.create("test-token", "alice", "Match one", "shared")
    api.create("test-token", "alice", "Match two", "shared")

    assert len(api.search("test-token", "alice", "shared", limit=1)) == 1


def test_maximum_title_length_is_accepted(api: NotesApi) -> None:
    """The documented title boundary is inclusive."""
    note_id = api.create("test-token", "alice", "x" * 120, "Text.")

    assert api.get("test-token", "alice", note_id)["title"] == "x" * 120


def test_search_escapes_underscore_wildcard(api: NotesApi) -> None:
    """Underscores match literal text rather than arbitrary characters."""
    api.create("test-token", "alice", "user_name", "Text.")
    api.create("test-token", "alice", "userXname", "Text.")

    assert [note["title"] for note in api.search("test-token", "alice", "_")] == ["user_name"]
