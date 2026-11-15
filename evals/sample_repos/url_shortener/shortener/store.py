# SQLite persistence for shortened URLs.
# User-controlled values are always supplied as SQL parameters.

import sqlite3
from contextlib import closing


def initialize(database_path: str) -> None:
    """Create the URL mapping table and lookup index."""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS short_urls (
                code TEXT PRIMARY KEY,
                destination TEXT NOT NULL,
                owner TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                visits INTEGER NOT NULL DEFAULT 0
            )
            """)
        connection.execute("CREATE INDEX IF NOT EXISTS short_urls_owner ON short_urls(owner)")
        connection.commit()


def save(database_path: str, code: str, destination: str, owner: str) -> None:
    """Persist one URL mapping."""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            "INSERT INTO short_urls (code, destination, owner) VALUES (?, ?, ?)",
            (code, destination, owner),
        )
        connection.commit()


def find(database_path: str, code: str) -> str | None:
    """Return the destination for a code and increment its visit count."""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT destination FROM short_urls WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            return None
        connection.execute("UPDATE short_urls SET visits = visits + 1 WHERE code = ?", (code,))
        connection.commit()
    return str(row[0])


def list_by_owner(database_path: str, owner: str) -> list[dict[str, object]]:
    """List mappings owned by a user, newest first."""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT code, destination, created_at, visits FROM short_urls "
            "WHERE owner = ? ORDER BY created_at DESC, code",
            (owner,),
        ).fetchall()
    return [dict(row) for row in rows]


def owner_stats(database_path: str, owner: str) -> dict[str, int]:
    """Return mapping and visit counts for one owner."""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(visits), 0) FROM short_urls WHERE owner = ?",
            (owner,),
        ).fetchone()
    return {"links": int(row[0]), "visits": int(row[1])}


def remove(database_path: str, code: str, owner: str) -> bool:
    """Remove a mapping only when it belongs to the given owner."""
    with closing(sqlite3.connect(database_path)) as connection:
        cursor = connection.execute(
            "DELETE FROM short_urls WHERE code = ? AND owner = ?", (code, owner)
        )
        connection.commit()
    return cursor.rowcount == 1
