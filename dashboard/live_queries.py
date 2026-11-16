# Dashboard operational queries for review traces, feedback, alerts, and drift.

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import streamlit as st

from dashboard.queries import _read_connection, database_path, list_eval_runs


def list_review_runs(limit: int = 100, path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return recent review runs from the read-only operational store."""
    resolved = Path(path) if path is not None else database_path()
    return _list_review_runs_cached(str(resolved.resolve()), limit)


@st.cache_data(ttl=15)
def _list_review_runs_cached(path: str, limit: int) -> list[dict[str, Any]]:
    connection = _read_connection(path)
    if connection is None:
        return []
    try:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        ]
    except sqlite3.Error:
        return []
    finally:
        connection.close()


def review_run_detail(
    run_id: str, path: str | Path | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Load findings, trace events, and human feedback for one review run."""
    resolved = Path(path) if path is not None else database_path()
    return _review_run_detail_cached(run_id, str(resolved.resolve()))


@st.cache_data(ttl=15)
def _review_run_detail_cached(run_id: str, path: str) -> dict[str, list[dict[str, Any]]]:
    connection = _read_connection(path)
    empty = {"findings": [], "events": [], "feedback": []}
    if connection is None:
        return empty
    try:
        result = {}
        for table in ("findings", "events", "feedback"):
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE run_id = ? ORDER BY "
                + ("id" if table == "events" else "rowid"),
                (run_id,),
            ).fetchall()
            result[table] = [dict(row) for row in rows]
        for event in result["events"]:
            try:
                event["payload"] = json.loads(event.get("payload") or "{}")
            except (TypeError, json.JSONDecodeError):
                event["payload"] = {}
        return result
    except sqlite3.Error:
        return empty
    finally:
        connection.close()


def live_alerts(since: str, path: str | Path | None = None) -> list[str]:
    """Return version-one alerts for failures and rates since an ISO timestamp."""
    resolved = Path(path) if path is not None else database_path()
    connection = _read_connection(resolved)
    if connection is None:
        return []
    try:
        rows = connection.execute(
            "SELECT kind, payload FROM events WHERE ts >= ?", (since,)
        ).fetchall()
        total = len(rows)
        json_failures = timeouts = errors = 0
        for row in rows:
            payload = str(row["payload"] or "").casefold()
            kind = str(row["kind"] or "").casefold()
            json_failures += int("json" in payload and ("fail" in payload or "invalid" in payload))
            timeouts += int("timeout" in payload or "timeout" in kind)
            errors += int(kind == "error" and "unhandled" in payload)
        alerts = []
        if total and json_failures / total > 0.05:
            alerts.append(
                f"JSON failure rate is {json_failures / total:.1%} over the last hour (limit 5%)."
            )
        if total and timeouts / total > 0.10:
            alerts.append(
                f"LLM timeout rate is {timeouts / total:.1%} over the last hour (limit 10%)."
            )
        if errors:
            alerts.append(f"{errors} run(s) recorded an unhandled error in the last hour.")
        return alerts
    except sqlite3.Error:
        return []
    finally:
        connection.close()


def review_drift(path: str | Path | None = None) -> dict[str, Any]:
    """Compare the latest 14-day pipeline replay metrics with the saved baseline."""
    runs = list_eval_runs(limit=500, path=path)
    baseline = next(
        (run for run in runs if run["layer"] == "pipeline" and run["is_baseline"]), None
    )
    if baseline is None:
        return {"baseline": None, "recent": None, "deltas": {}}

    cutoff = (datetime.now(UTC) - timedelta(days=14)).isoformat()
    recent = next(
        (run for run in runs if run["layer"] == "pipeline" and run["started_at"] >= cutoff), None
    )
    if recent is None:
        return {"baseline": baseline, "recent": None, "deltas": {}}
    try:
        old = json.loads(baseline["summary"] or "{}")
        new = json.loads(recent["summary"] or "{}")
    except (TypeError, json.JSONDecodeError):
        old, new = {}, {}
    deltas = {
        key: new[key] - old[key]
        for key in old.keys() & new.keys()
        if isinstance(old[key], (int, float)) and isinstance(new[key], (int, float))
    }
    return {"baseline": baseline, "recent": recent, "deltas": deltas}
