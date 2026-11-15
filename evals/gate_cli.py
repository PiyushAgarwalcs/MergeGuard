# Loads the committed baseline and latest saved runs for a CI regression check.
# Missing layers fail explicitly so a partial pull-request tier cannot pass.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.baseline import BASELINE_PATH
from evals.gates import GateReport, evaluate_regression
from mergeguard.storage import connect, get_eval_bundle, list_eval_runs

PULL_REQUEST_LAYERS = {
    "components",
    "integration",
    "robustness",
    "agent_security",
    "agents_other",
    "pipeline",
}


def saved_regression_report(
    baseline_path: Path = BASELINE_PATH, *, connection: Any = None
) -> GateReport:
    """Compare each committed baseline layer with the newest different saved run."""
    if not baseline_path.is_file():
        raise ValueError(f"Regression baseline does not exist: {baseline_path}")
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline = payload.get("layers")
    if not isinstance(baseline, dict) or not baseline:
        raise ValueError("Regression baseline must contain a non-empty layers mapping.")
    owns_connection = connection is None
    store = connection or connect()
    try:
        runs = list_eval_runs(limit=1000, connection=store)
        candidates = {}
        compared_baseline = {
            layer: record for layer, record in baseline.items() if layer in PULL_REQUEST_LAYERS
        }
        failures = []
        for layer, record in compared_baseline.items():
            baseline_id = record.get("eval_run_id")
            candidate_run = next(
                (
                    run
                    for run in runs
                    if run["layer"] == layer and run["eval_run_id"] != baseline_id
                ),
                None,
            )
            if candidate_run is None:
                failures.append(f"{layer}: no new evaluation run exists to compare with baseline.")
                continue
            bundle = get_eval_bundle(candidate_run["eval_run_id"], connection=store)
            if bundle is not None:
                candidates[layer] = _decode_bundle(bundle)
        report = evaluate_regression(compared_baseline, candidates)
    finally:
        if owns_connection:
            store.close()
    return GateReport(
        report.passed and not failures,
        tuple(failures) + report.failures,
        report.warnings,
    )


def _decode_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Convert SQLite JSON columns into the baseline comparison shape."""
    return {
        "summary": _decode(bundle["summary"]),
        "results": [
            {
                **row,
                "expected": _decode(row["expected"]),
                "actual": _decode(row["actual"]),
                "metrics": _decode(row["metrics"]),
            }
            for row in bundle["results"]
        ],
    }


def _decode(value: Any) -> Any:
    """Decode a JSON string while accepting already-parsed values."""
    return json.loads(value) if isinstance(value, str) else value
