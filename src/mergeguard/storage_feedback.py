# mergeguard.storage_feedback
# Persists human feedback and webhook delivery idempotency records.

from __future__ import annotations

import sqlite3
from typing import Any

from mergeguard.storage import _utciso, _with_connection


def insert_feedback(
    run_id: str,
    finding_id: str,
    action: str,
    by_user: str,
    reason: str,
    *,
    ts: str | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    row = {
        "run_id": run_id,
        "finding_id": finding_id,
        "action": action,
        "by_user": by_user,
        "reason": reason,
        "ts": ts or _utciso(),
    }

    def _op(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            "INSERT INTO feedback (run_id, finding_id, action, by_user, reason, ts) VALUES (?, ?, ?, ?, ?, ?)",
            (
                row["run_id"],
                row["finding_id"],
                row["action"],
                row["by_user"],
                row["reason"],
                row["ts"],
            ),
        )
        conn.commit()
        return row

    return _with_connection(connection, _op)


def insert_delivery(
    delivery_id: str,
    *,
    received_at: str | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    row = {"delivery_id": delivery_id, "received_at": received_at or _utciso()}

    def _op(conn: sqlite3.Connection) -> dict[str, Any]:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO deliveries (delivery_id, received_at) VALUES (?, ?)",
            (row["delivery_id"], row["received_at"]),
        )
        conn.commit()
        return {**row, "inserted": cursor.rowcount == 1}

    return _with_connection(connection, _op)
