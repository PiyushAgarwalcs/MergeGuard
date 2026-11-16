# mergeguard.storage_evals
# Persists evaluation run summaries and per-case outcomes.

from __future__ import annotations

import sqlite3
from typing import Any

from mergeguard.storage import _utciso, _with_connection


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
