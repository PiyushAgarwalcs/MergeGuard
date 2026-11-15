# Read-only queries and dataset review-log helpers for dashboard pages.
# All evaluation SQL lives here; review decisions never rewrite case labels.

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import streamlit as st
import yaml

from mergeguard.settings import DATABASE_PATH

DATASET_ROOT = Path(__file__).resolve().parents[1] / "evals" / "datasets"
REVIEW_ACTIONS = {"accept", "reject", "edit"}


def database_path() -> Path:
    """Resolve the dashboard database path from the current environment."""
    return Path(os.environ.get("DATABASE_PATH", DATABASE_PATH)).expanduser().resolve()


def _read_connection(path: str | Path | None = None) -> sqlite3.Connection | None:
    """Open an existing SQLite file in read-only mode, or return no connection."""
    resolved = Path(path) if path is not None else database_path()
    if not resolved.exists():
        return None
    uri = f"file:{resolved.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    connection.row_factory = sqlite3.Row
    return connection


def list_eval_runs(limit: int = 50, path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return recent evaluation run summaries without opening a write connection."""
    resolved = Path(path) if path is not None else database_path()
    return _list_eval_runs_cached(str(resolved.resolve()), limit)


@st.cache_data(ttl=30)
def _list_eval_runs_cached(path: str, limit: int) -> list[dict[str, Any]]:
    """Cache recent runs by resolved database path for thirty seconds."""
    connection = _read_connection(path)
    if connection is None:
        return []
    try:
        rows = connection.execute(
            "SELECT * FROM eval_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        return []
    finally:
        connection.close()


def list_eval_results(eval_run_id: str, path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return per-case outcomes for one evaluation run."""
    resolved = Path(path) if path is not None else database_path()
    return _list_eval_results_cached(eval_run_id, str(resolved.resolve()))


def latest_eval_run(layer: str, path: str | Path | None = None) -> dict[str, Any] | None:
    """Return the most recent evaluation run for one layer."""
    return next(
        (run for run in list_eval_runs(limit=500, path=path) if run["layer"] == layer), None
    )


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
    from datetime import timedelta

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


def list_llm_event_summaries(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Aggregate recorded model calls by node without exposing prompt contents."""
    resolved = Path(path) if path is not None else database_path()
    return _list_llm_event_summaries_cached(str(resolved.resolve()))


@st.cache_data(ttl=30)
def _list_llm_event_summaries_cached(path: str) -> list[dict[str, Any]]:
    connection = _read_connection(path)
    if connection is None:
        return []
    try:
        rows = connection.execute("""SELECT node, COUNT(*) AS calls, SUM(tokens_in) AS tokens_in,
                      SUM(tokens_out) AS tokens_out, SUM(cost_usd) AS cost_usd,
                      AVG(latency_ms) AS mean_latency_ms
               FROM events WHERE kind = 'llm_call' GROUP BY node ORDER BY node""").fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        return []
    finally:
        connection.close()


@st.cache_data(ttl=30)
def _list_eval_results_cached(eval_run_id: str, path: str) -> list[dict[str, Any]]:
    """Cache one evaluation's outcomes by run and resolved database path."""
    connection = _read_connection(path)
    if connection is None:
        return []
    try:
        rows = connection.execute(
            "SELECT * FROM eval_results WHERE eval_run_id = ? ORDER BY case_id, repeat",
            (eval_run_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        return []
    finally:
        connection.close()


def load_dataset_cases(version: str, root: Path = DATASET_ROOT) -> list[dict[str, Any]]:
    """Load case labels and diffs in stable id order for browser display."""
    return _load_dataset_cases_cached(version, str(root.resolve()))


@st.cache_data(ttl=30)
def _load_dataset_cases_cached(version: str, root: str) -> list[dict[str, Any]]:
    """Cache case data briefly while preserving version and root isolation."""
    records = []
    case_root = Path(root) / version / "cases"
    for case_file in sorted(case_root.glob("*/case.yml")):
        record = yaml.safe_load(case_file.read_text(encoding="utf-8"))
        record["diff"] = (case_file.parent / "change.diff").read_text(encoding="utf-8")
        records.append(record)
    return records


def dataset_counts(version: str, root: Path = DATASET_ROOT) -> dict[str, Any]:
    """Count cases by source, category, split and tier."""
    records = load_dataset_cases(version, root)
    return {
        "total": len(records),
        "source": _count(records, "source"),
        "category": _count(records, "category"),
        "split": _count(records, "split"),
        "tier": _count(records, "tier"),
    }


def load_review_log(version: str, root: Path = DATASET_ROOT) -> list[dict[str, Any]]:
    """Read prior review actions from the append-only JSONL log."""
    log_path = root / version / "review_log.jsonl"
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def append_review_action(
    version: str,
    case_id: str,
    action: str,
    reviewer: str,
    reason: str,
    root: Path = DATASET_ROOT,
) -> dict[str, str]:
    """Append one review action after confirming the case exists."""
    if action not in REVIEW_ACTIONS:
        raise ValueError(f"Action must be one of {sorted(REVIEW_ACTIONS)}.")
    case_root = (root / version / "cases").resolve()
    case_path = (case_root / case_id / "case.yml").resolve()
    if not case_path.is_relative_to(case_root) or not case_path.is_file():
        raise ValueError("Review action refers to an unknown case.")
    record = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "version": version,
        "case_id": case_id,
        "action": action,
        "reviewer": reviewer.strip(),
        "reason": reason.strip(),
    }
    log_path = root / version / "review_log.jsonl"
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def _count(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    """Return stable counts for one case metadata key."""
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
