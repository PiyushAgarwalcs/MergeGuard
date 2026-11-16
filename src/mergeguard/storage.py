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


from mergeguard.storage_eval_queries import get_eval_bundle, list_eval_runs, mark_eval_baselines
from mergeguard.storage_evals import (
    insert_eval_bundle,
    insert_eval_result,
    insert_eval_run,
)
from mergeguard.storage_events import (
    get_events,
    get_findings,
    insert_event,
    insert_finding,
)
from mergeguard.storage_feedback import insert_delivery, insert_feedback
from mergeguard.storage_runs import find_review_run, get_run, insert_run, list_runs

__all__ = [
    "connect",
    "find_review_run",
    "get_eval_bundle",
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
    "mark_eval_baselines",
    "migrate",
]
