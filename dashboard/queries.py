# Read-only evaluation and dataset queries for dashboard pages.
# All evaluation SQL lives here; dashboards do not modify project data.

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import streamlit as st
import yaml

from mergeguard.settings import DATABASE_PATH

DATASET_ROOT = Path(__file__).resolve().parents[1] / "evals" / "datasets"


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


def _count(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    """Return stable counts for one case metadata key."""
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
