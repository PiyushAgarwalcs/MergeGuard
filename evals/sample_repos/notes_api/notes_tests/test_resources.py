# Resource-lifetime tests for sample database helpers.
# Tracking wrappers expose connections that SQLite normally closes silently.

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Self

import pytest
from notes_api import db


class TrackingConnection:
    """Proxy a SQLite connection while recording explicit close calls."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the wrapped connection and initialize its close state."""
        self.connection = connection
        self.closed = False

    def __getattr__(self, name: str):
        """Forward ordinary SQLite operations to the wrapped connection."""
        return getattr(self.connection, name)

    def close(self) -> None:
        """Close the wrapped connection and record the operation."""
        self.closed = True
        self.connection.close()

    def __enter__(self) -> Self:
        """Return the proxy for a connection context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Delegate transaction handling without closing the connection."""
        self.connection.__exit__(*args)


@pytest.mark.parametrize("operation", ["select_note", "select_notes"])
def test_database_reads_close_connections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """Read helpers explicitly close their SQLite connection."""
    database_path = str(tmp_path / "notes.sqlite")
    db.initialize(database_path)
    note_id = db.insert_note(database_path, "alice", "Title", "Body.")
    real_connect = db.connect
    connections: list[TrackingConnection] = []

    def tracked_connect(path: str) -> TrackingConnection:
        """Wrap each opened connection so its lifetime can be asserted."""
        connection = TrackingConnection(real_connect(path))
        connections.append(connection)
        return connection

    monkeypatch.setattr(db, "connect", tracked_connect)
    if operation == "select_note":
        db.select_note(database_path, "alice", note_id)
    else:
        db.select_notes(database_path, "alice")

    assert connections[0].closed
