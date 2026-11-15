# Compares saved evaluation runs and writes reproducible baseline snapshots.
# Paired case outcomes provide intervals and make regressions easy to inspect.

from __future__ import annotations

import json
import math
from typing import Any

from evals.stats import paired_bootstrap_difference
from mergeguard.storage import connect, get_eval_bundle


def compare_runs(baseline_id: str, candidate_id: str, *, connection: Any = None) -> dict[str, Any]:
    """Compare numeric metrics and case outcomes for two saved runs."""
    owns_connection = connection is None
    store = connection or connect()
    try:
        baseline = get_eval_bundle(baseline_id, connection=store)
        candidate = get_eval_bundle(candidate_id, connection=store)
    finally:
        if owns_connection:
            store.close()
    if baseline is None or candidate is None:
        raise ValueError("Both evaluation run IDs must exist in the results database.")
    if baseline["layer"] != candidate["layer"]:
        raise ValueError("Evaluation runs must use the same layer.")
    old_metrics = _decode(baseline["summary"])
    new_metrics = _decode(candidate["summary"])
    metrics = _compare_metrics(baseline["results"], candidate["results"], old_metrics, new_metrics)
    return {
        "baseline_id": baseline_id,
        "candidate_id": candidate_id,
        "layer": baseline["layer"],
        "metrics": metrics,
        "flipped_cases": _flipped_cases(baseline["results"], candidate["results"]),
    }


def render_markdown(comparison: dict[str, Any]) -> str:
    """Render a concise comparison suitable for a pull request comment."""
    lines = [
        f"## Evaluation comparison: {comparison['layer']}",
        "",
        f"Baseline `{comparison['baseline_id']}` → candidate `{comparison['candidate_id']}`",
        "",
        "| Metric | Baseline | Candidate | Delta (95% paired interval) | N |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, item in sorted(comparison["metrics"].items()):
        interval = item["interval"]
        delta = f"{item['delta']:+.4f}"
        if interval is not None:
            delta += f" [{interval[0]:+.4f}, {interval[1]:+.4f}]"
        lines.append(
            f"| {name} | {item['baseline']:.4f} | {item['candidate']:.4f} | "
            f"{delta} | {item['n']} |"
        )
    lines.extend(["", "### Flipped cases", ""])
    flips = comparison["flipped_cases"]
    if not flips:
        lines.append("No case outcomes changed.")
    else:
        lines.extend(
            f"- `{item['case_id']}` repeat {item['repeat']}: "
            f"{item['baseline']} → {item['candidate']}"
            for item in flips
        )
    return "\n".join(lines)


def _compare_metrics(
    old_rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    old_summary: dict[str, Any],
    new_summary: dict[str, Any],
) -> dict[str, Any]:
    """Calculate candidate-minus-baseline deltas and paired bootstrap intervals."""
    names = {
        name
        for row in old_rows + new_rows
        for name, value in _decode(row["metrics"]).items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    result = {}
    for name in sorted(names):
        old, new = _paired_values(old_rows, new_rows, name)
        if not old:
            continue
        interval = paired_bootstrap_difference(old, new)
        result[name] = {
            "baseline": sum(old) / len(old),
            "candidate": sum(new) / len(new),
            "delta": interval.difference,
            "interval": [interval.lower, interval.upper],
            "n": len(old),
        }
    for name in old_summary.keys() & new_summary.keys():
        old_value, new_value = old_summary[name], new_summary[name]
        if name in result or not _is_number(old_value) or not _is_number(new_value):
            continue
        result[name] = {
            "baseline": float(old_value),
            "candidate": float(new_value),
            "delta": float(new_value) - float(old_value),
            "interval": None,
            "n": 0,
        }
    return result


def _paired_values(
    old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]], metric: str
) -> tuple[list[float], list[float]]:
    old_map = {_case_key(row): _decode(row["metrics"]) for row in old_rows}
    new_map = {_case_key(row): _decode(row["metrics"]) for row in new_rows}
    keys = sorted(old_map.keys() & new_map.keys())
    keys = [
        key
        for key in keys
        if _is_number(old_map[key].get(metric)) and _is_number(new_map[key].get(metric))
    ]
    return [float(old_map[key][metric]) for key in keys], [
        float(new_map[key][metric]) for key in keys
    ]


def _flipped_cases(
    old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """List shared cases whose pass flag or reported outcome changed."""
    old = {_case_key(row): row for row in old_rows}
    new = {_case_key(row): row for row in new_rows}
    flips = []
    for key in sorted(old.keys() & new.keys()):
        old_row, new_row = old[key], new[key]
        old_outcome = _decode(old_row["actual"]).get("outcome", bool(old_row["passed"]))
        new_outcome = _decode(new_row["actual"]).get("outcome", bool(new_row["passed"]))
        if bool(old_row["passed"]) != bool(new_row["passed"]) or old_outcome != new_outcome:
            flips.append(
                {
                    "case_id": key[0],
                    "repeat": key[1],
                    "baseline": old_outcome,
                    "candidate": new_outcome,
                }
            )
    return flips


def _case_key(row: dict[str, Any]) -> tuple[str, int]:
    """Return the stable case and repeat identity."""
    return str(row["case_id"]), int(row["repeat"])


def _decode(value: Any) -> Any:
    """Decode JSON columns while accepting already-decoded values."""
    return json.loads(value) if isinstance(value, str) else value


def _is_number(value: Any) -> bool:
    """Accept finite numeric metric values but exclude booleans and NaN."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
