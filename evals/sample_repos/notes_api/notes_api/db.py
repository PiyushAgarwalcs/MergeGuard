# SQLite persistence for the sample notes service.
# Each operation uses parameterized SQL and closes its own connection.

import sqlite3
from contextlib import closing


def connect(database_path: str) -> sqlite3.Connection:
    """Open a database connection with row access by column name."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize(database_path: str) -> None:
    """Create the notes table when it does not exist."""
    with closing(connect(database_path)) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)
        connection.commit()


def insert_note(database_path: str, user_id: str, title: str, body: str) -> int:
    """Insert a note and return its generated id."""
    with closing(connect(database_path)) as connection:
        cursor = connection.execute(
            "INSERT INTO notes (user_id, title, body) VALUES (?, ?, ?)",
            (user_id, title, body),
        )
        connection.commit()
        return int(cursor.lastrowid)


def select_note(database_path: str, user_id: str, note_id: int) -> dict | None:
    """Read one note only when it belongs to the requesting user."""
    with closing(connect(database_path)) as connection:
        row = connection.execute(
            "SELECT id, user_id, title, body, created_at FROM notes "
            "WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        ).fetchone()
    return dict(row) if row is not None else None


def select_notes(database_path: str, user_id: str) -> list[dict]:
    """List a user's notes in creation order."""
    with closing(connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT id, user_id, title, body, created_at FROM notes "
            "WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def search_notes(database_path: str, user_id: str, term: str, limit: int) -> list[dict]:
    """Search titles and bodies without treating input wildcards as patterns."""
    escaped_term = term.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    with closing(connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT id, user_id, title, body, created_at FROM notes "
            "WHERE user_id = ? AND (title LIKE ? ESCAPE '!' OR body LIKE ? ESCAPE '!') "
            "ORDER BY id LIMIT ?",
            (user_id, f"%{escaped_term}%", f"%{escaped_term}%", limit),
        ).fetchall()
    return [dict(row) for row in rows]


def update_note(database_path: str, user_id: str, note_id: int, title: str, body: str) -> bool:
    """Update a note only when it belongs to the requesting user."""
    with closing(connect(database_path)) as connection:
        cursor = connection.execute(
            "UPDATE notes SET title = ?, body = ? WHERE id = ? AND user_id = ?",
            (title, body, note_id, user_id),
        )
        connection.commit()
    return cursor.rowcount == 1


def delete_note(database_path: str, user_id: str, note_id: int) -> bool:
    """Delete one note only when it belongs to the requesting user."""
    with closing(connect(database_path)) as connection:
        cursor = connection.execute(
            "DELETE FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        )
        connection.commit()
    return cursor.rowcount == 1
