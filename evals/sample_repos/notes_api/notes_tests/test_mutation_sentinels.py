# Regression sentinels for correctness mutations in the notes sample.
# Defaults and required identities are observable public behavior.

import pytest
from notes_api.api import NotesApi
from notes_api.config import load_settings
from notes_api.db import initialize


def test_default_database_location_is_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing database setting uses the documented local file name."""
    monkeypatch.delenv("NOTES_DATABASE", raising=False)

    assert load_settings().database_path == "notes.db"


def test_none_user_is_rejected_as_unauthenticated(tmp_path) -> None:
    """Missing identity data is rejected with the service's permission error."""
    database_path = str(tmp_path / "notes.sqlite")
    initialize(database_path)
    api = NotesApi(database_path, "test-token")

    with pytest.raises(PermissionError):
        api.list("test-token", None)
