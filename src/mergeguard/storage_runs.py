# mergeguard.storage_runs
# Persists runs records for review runs.

from __future__ import annotations

import sqlite3
from typing import Any

from mergeguard.storage import _row_to_dict, _utciso, _with_connection


def insert_run(
    run_id: str,
    repo: str | None = None,
    pr_number: int | None = None,
    head_sha: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    status: str | None = None,
    outcome: str | None = None,
    code_version: str | None = None,
    prompt_versions: str | None = None,
    model_config: str | None = None,
    total_cost_usd: float | None = None,
    total_ms: int | None = None,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    started = started_at or _utciso()
    payload = {
        "run_id": run_id,
        "repo": repo,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "started_at": started,
        "finished_at": finished_at,
        "status": status,
        "outcome": outcome,
        "code_version": code_version,
        "prompt_versions": prompt_versions,
        "model_config": model_config,
        "total_cost_usd": total_cost_usd,
        "total_ms": total_ms,
    }

    def _op(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, repo, pr_number, head_sha, started_at, finished_at, status,
                outcome, code_version, prompt_versions, model_config, total_cost_usd,
                total_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                repo=excluded.repo,
                pr_number=excluded.pr_number,
                head_sha=excluded.head_sha,
                started_at=excluded.started_at,
                finished_at=excluded.finished_at,
                status=excluded.status,
                outcome=excluded.outcome,
                code_version=excluded.code_version,
                prompt_versions=excluded.prompt_versions,
                model_config=excluded.model_config,
                total_cost_usd=excluded.total_cost_usd,
                total_ms=excluded.total_ms
            """,
            (
                run_id,
                repo,
                pr_number,
                head_sha,
                started,
                finished_at,
                status,
                outcome,
                code_version,
                prompt_versions,
                model_config,
                total_cost_usd,
                total_ms,
            ),
        )
        conn.commit()
        return payload

    return _with_connection(connection, _op)


def get_run(run_id: str, *, connection: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    def _op(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _row_to_dict(row)

    return _with_connection(connection, _op)


def find_review_run(
    repo: str,
    pr_number: int,
    head_sha: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """Find the existing review for one repository, PR number and exact head SHA."""

    def _op(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            """SELECT * FROM runs WHERE repo = ? AND pr_number = ? AND head_sha = ?
               ORDER BY started_at DESC LIMIT 1""",
            (repo, pr_number, head_sha),
        ).fetchone()
        return _row_to_dict(row)

    return _with_connection(connection, _op)


def list_runs(
    limit: int = 50, *, connection: sqlite3.Connection | None = None
) -> list[dict[str, Any]]:
    def _op(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            item = _row_to_dict(row)
            if item is not None:
                results.append(item)
        return results

    return _with_connection(connection, _op)
