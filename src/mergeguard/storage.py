# mergeguard.storage
# Owns the SQLite database and persistence for runs, metadata and review state.

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from mergeguard.settings import DATABASE_PATH


def _db_path(path: str | Path | None = None) -> Path:
    resolved = Path(path or DATABASE_PATH)
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _utciso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


_INITIALIZE_LOCK = threading.Lock()


def _initialize_connection(connection: sqlite3.Connection) -> None:
    with _INITIALIZE_LOCK:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              repo TEXT,
              pr_number INT,
              head_sha TEXT,
              started_at TEXT,
              finished_at TEXT,
              status TEXT,
              outcome TEXT,
              code_version TEXT,
              prompt_versions TEXT,
              model_config TEXT,
              total_cost_usd REAL,
              total_ms INT)
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY,
              run_id TEXT,
              ts TEXT,
              node TEXT,
              kind TEXT,
              model TEXT,
              prompt_version TEXT,
              tokens_in INT,
              tokens_out INT,
              cost_usd REAL,
              latency_ms INT,
              payload TEXT)
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS findings (
              run_id TEXT,
              finding_id TEXT,
              source TEXT,
              category TEXT,
              severity TEXT,
              file TEXT,
              line_start INT,
              line_end INT,
              quote TEXT,
              verified INT,
              skeptic_verdict TEXT,
              status TEXT)
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
              run_id TEXT,
              finding_id TEXT,
              action TEXT,
              by_user TEXT,
              reason TEXT,
              ts TEXT)
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
              delivery_id TEXT PRIMARY KEY,
              received_at TEXT)
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs (
              eval_run_id TEXT PRIMARY KEY,
              started_at TEXT,
              layer TEXT,
              dataset_version TEXT,
              code_version TEXT,
              prompt_versions TEXT,
              model_config TEXT,
              repeats INT,
              is_baseline INT,
              summary TEXT)
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS eval_results (
              eval_run_id TEXT,
              case_id TEXT,
              repeat INT,
              passed INT,
              expected TEXT,
              actual TEXT,
              metrics TEXT,
              run_id TEXT)
            """)
        connection.commit()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(_db_path(path), timeout=5.0)
    _initialize_connection(connection)
    return connection


def migrate(connection: sqlite3.Connection | None = None) -> sqlite3.Connection:
    if connection is None:
        return connect()
    _initialize_connection(connection)
    return connection


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}  # noqa: SIM118


T = TypeVar("T")


def _with_connection(
    connection: sqlite3.Connection | None,
    callback: Callable[[sqlite3.Connection], T],
) -> T:
    owns = connection is None
    conn = connection or connect()
    try:
        return callback(conn)
    finally:
        if owns:
            conn.close()


def _parse_json(value: str | None) -> Any:
    if value in {None, ""}:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


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


def insert_event(
    run_id: str,
    node: str,
    kind: str,
    payload: str | dict[str, Any] | None = None,
    *,
    ts: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    text_value = (
        payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, default=str)
    )
    row = {
        "run_id": run_id,
        "ts": ts or _utciso(),
        "node": node,
        "kind": kind,
        "model": model,
        "prompt_version": prompt_version,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "payload": text_value,
    }

    def _op(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            """
            INSERT INTO events (
                run_id, ts, node, kind, model, prompt_version, tokens_in, tokens_out,
                cost_usd, latency_ms, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["run_id"],
                row["ts"],
                row["node"],
                row["kind"],
                row["model"],
                row["prompt_version"],
                row["tokens_in"],
                row["tokens_out"],
                row["cost_usd"],
                row["latency_ms"],
                row["payload"],
            ),
        )
        conn.commit()
        return row

    return _with_connection(connection, _op)


def get_events(
    run_id: str, *, connection: sqlite3.Connection | None = None
) -> list[dict[str, Any]]:
    def _op(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT * FROM events WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        parsed: list[dict[str, Any]] = []
        for row in rows:
            event = _row_to_dict(row)
            if event is not None:
                event["payload"] = _parse_json(event.get("payload"))
                parsed.append(event)
        return parsed

    return _with_connection(connection, _op)


def insert_finding(
    run_id: str,
    finding: dict[str, Any] | Any,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    if hasattr(finding, "model_dump"):
        payload = finding.model_dump()
    elif hasattr(finding, "dict"):
        payload = finding.dict()
    else:
        payload = dict(finding)
    row = {
        "run_id": run_id,
        "finding_id": payload.get("id"),
        "source": payload.get("source"),
        "category": payload.get("category"),
        "severity": payload.get("severity"),
        "file": payload.get("file"),
        "line_start": payload.get("line_start"),
        "line_end": payload.get("line_end"),
        "quote": payload.get("quote"),
        "verified": 1 if payload.get("verified") else 0,
        "skeptic_verdict": payload.get("skeptic_verdict"),
        "status": payload.get("status", "shown"),
    }

    def _op(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            """
            INSERT INTO findings (
                run_id, finding_id, source, category, severity, file, line_start,
                line_end, quote, verified, skeptic_verdict, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["run_id"],
                row["finding_id"],
                row["source"],
                row["category"],
                row["severity"],
                row["file"],
                row["line_start"],
                row["line_end"],
                row["quote"],
                row["verified"],
                row["skeptic_verdict"],
                row["status"],
            ),
        )
        conn.commit()
        return row

    return _with_connection(connection, _op)


def get_findings(
    run_id: str, *, connection: sqlite3.Connection | None = None
) -> list[dict[str, Any]]:
    def _op(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute("SELECT * FROM findings WHERE run_id = ?", (run_id,)).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            item = _row_to_dict(row)
            if item is not None:
                results.append(item)
        return results

    return _with_connection(connection, _op)


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


def insert_eval_run(
    eval_run_id: str,
    layer: str,
    dataset_version: str,
    code_version: str,
    prompt_versions: str,
    model_config: str,
    repeats: int,
    is_baseline: int,
    summary: str,
    *,
    started_at: str | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    row = {
        "eval_run_id": eval_run_id,
        "started_at": started_at or _utciso(),
        "layer": layer,
        "dataset_version": dataset_version,
        "code_version": code_version,
        "prompt_versions": prompt_versions,
        "model_config": model_config,
        "repeats": repeats,
        "is_baseline": is_baseline,
        "summary": summary,
    }

    def _op(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            """
            INSERT INTO eval_runs (
                eval_run_id, started_at, layer, dataset_version, code_version,
                prompt_versions, model_config, repeats, is_baseline, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["eval_run_id"],
                row["started_at"],
                row["layer"],
                row["dataset_version"],
                row["code_version"],
                row["prompt_versions"],
                row["model_config"],
                row["repeats"],
                row["is_baseline"],
                row["summary"],
            ),
        )
        conn.commit()
        return row

    return _with_connection(connection, _op)


def insert_eval_result(
    eval_run_id: str,
    case_id: str,
    repeat: int,
    passed: int,
    expected: str,
    actual: str,
    metrics: str,
    run_id: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    row = {
        "eval_run_id": eval_run_id,
        "case_id": case_id,
        "repeat": repeat,
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "metrics": metrics,
        "run_id": run_id,
    }

    def _op(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            """
            INSERT INTO eval_results (
                eval_run_id, case_id, repeat, passed, expected, actual, metrics, run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["eval_run_id"],
                row["case_id"],
                row["repeat"],
                row["passed"],
                row["expected"],
                row["actual"],
                row["metrics"],
                row["run_id"],
            ),
        )
        conn.commit()
        return row

    return _with_connection(connection, _op)


def insert_eval_bundle(
    run: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Atomically save one evaluation run and its per-case result rows."""

    def _op(conn: sqlite3.Connection) -> dict[str, Any]:
        with conn:
            conn.execute(
                """
                INSERT INTO eval_runs (
                    eval_run_id, started_at, layer, dataset_version, code_version,
                    prompt_versions, model_config, repeats, is_baseline, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run["eval_run_id"],
                    run["started_at"],
                    run["layer"],
                    run["dataset_version"],
                    run["code_version"],
                    run["prompt_versions"],
                    run["model_config"],
                    run["repeats"],
                    run["is_baseline"],
                    run["summary"],
                ),
            )
            conn.executemany(
                """
                INSERT INTO eval_results (
                    eval_run_id, case_id, repeat, passed, expected, actual, metrics, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run["eval_run_id"],
                        item["case_id"],
                        item["repeat"],
                        item["passed"],
                        item["expected"],
                        item["actual"],
                        item["metrics"],
                        item["run_id"],
                    )
                    for item in results
                ],
            )
        return {**run, "case_count": len(results)}

    return _with_connection(connection, _op)


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


__all__ = [
    "connect",
    "find_review_run",
    "get_events",
    "get_findings",
    "get_run",
    "insert_delivery",
    "insert_eval_bundle",
    "insert_eval_result",
    "insert_eval_run",
    "insert_event",
    "insert_feedback",
    "insert_finding",
    "insert_run",
    "list_eval_runs",
    "list_runs",
    "migrate",
]
