# mergeguard.storage_eval_queries
# Reads saved evaluation bundles and marks reviewed baseline records.

from __future__ import annotations

import sqlite3
from typing import Any

from mergeguard.storage import _with_connection


def list_eval_runs(
    limit: int = 200, *, connection: sqlite3.Connection | None = None
) -> list[dict[str, Any]]:
    """Return saved evaluation runs from newest to oldest."""

    def _op(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT * FROM eval_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    return _with_connection(connection, _op)


def get_eval_bundle(
    eval_run_id: str, *, connection: sqlite3.Connection | None = None
) -> dict[str, Any] | None:
    """Load one evaluation run with its ordered per-case results."""

    def _op(conn: sqlite3.Connection) -> dict[str, Any] | None:
        run = conn.execute(
            "SELECT * FROM eval_runs WHERE eval_run_id = ?", (eval_run_id,)
        ).fetchone()
        if run is None:
            return None
        results = conn.execute(
            "SELECT * FROM eval_results WHERE eval_run_id = ? ORDER BY case_id, repeat",
            (eval_run_id,),
        ).fetchall()
        return {**dict(run), "results": [dict(item) for item in results]}

    return _with_connection(connection, _op)


def mark_eval_baselines(
    eval_run_ids: list[str], *, connection: sqlite3.Connection | None = None
) -> None:
    """Mark the selected saved evaluations as the active baseline records."""

    def _op(conn: sqlite3.Connection) -> None:
        with conn:
            conn.execute("UPDATE eval_runs SET is_baseline = 0")
            conn.executemany(
                "UPDATE eval_runs SET is_baseline = 1 WHERE eval_run_id = ?",
                [(run_id,) for run_id in eval_run_ids],
            )

    _with_connection(connection, _op)
