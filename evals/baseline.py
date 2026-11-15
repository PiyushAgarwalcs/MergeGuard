# Saves selected evaluation runs and per-case results as the active baseline.
# The JSON snapshot stays reviewable and can be compared by later CI runs.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mergeguard.storage import connect, get_eval_bundle, list_eval_runs, mark_eval_baselines

BASELINE_PATH = Path(__file__).with_name("baselines") / "main.json"


def save_baselines(path: Path = BASELINE_PATH, *, connection: Any = None) -> dict[str, Any]:
    """Snapshot the newest saved evaluation for each layer into JSON."""
    owns_connection = connection is None
    store = connection or connect()
    try:
        runs = list_eval_runs(limit=1000, connection=store)
        latest: dict[str, dict[str, Any]] = {}
        for run in runs:
            latest.setdefault(run["layer"], run)
        if not latest:
            raise ValueError("No saved evaluation runs are available to baseline.")
        selected: dict[str, Any] = {}
        for layer, run in latest.items():
            bundle = get_eval_bundle(run["eval_run_id"], connection=store)
            if bundle is None:
                raise ValueError(f"Evaluation run disappeared while saving baseline: {layer}.")
            selected[layer] = _baseline_record(bundle)
        mark_eval_baselines(
            [record["eval_run_id"] for record in selected.values()], connection=store
        )
    finally:
        if owns_connection:
            store.close()
    payload = {
        "version": 1,
        "saved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "layers": selected,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _baseline_record(bundle: dict[str, Any]) -> dict[str, Any]:
    """Copy the run metadata and per-case values needed for future comparisons."""
    return {
        "eval_run_id": bundle["eval_run_id"],
        "code_version": bundle["code_version"],
        "dataset_version": bundle["dataset_version"],
        "model_config": _decode(bundle["model_config"]),
        "summary": _decode(bundle["summary"]),
        "results": [
            {
                "case_id": row["case_id"],
                "repeat": row["repeat"],
                "passed": bool(row["passed"]),
                "expected": _decode(row["expected"]),
                "actual": _decode(row["actual"]),
                "metrics": _decode(row["metrics"]),
            }
            for row in bundle["results"]
        ],
    }


def _decode(value: Any) -> Any:
    """Decode a SQLite JSON column, accepting already-decoded values."""
    return json.loads(value) if isinstance(value, str) else value
