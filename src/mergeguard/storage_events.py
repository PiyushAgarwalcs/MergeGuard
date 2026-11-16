# mergeguard.storage_events
# Persists events records for review runs.

from __future__ import annotations

import json
import sqlite3
from typing import Any

from mergeguard.storage import _parse_json, _row_to_dict, _utciso, _with_connection


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
