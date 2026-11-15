# Compares saved runs from the same layer and lists changed case outcomes.
# All source rows come from the read-only query module.

import json

import pandas as pd
import streamlit as st

from dashboard.queries import list_eval_results, list_eval_runs


def _label(run: dict) -> str:
    """Format a run picker label without truncating its identity."""
    return f"{run['layer']} · {run['started_at']} · {run['eval_run_id']}"


def _summary(run: dict) -> dict:
    """Decode a saved summary into a mapping, tolerating malformed rows."""
    try:
        value = json.loads(run["summary"] or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _decode(value: str) -> dict:
    """Parse one case JSON field into a mapping."""
    try:
        result = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return result if isinstance(result, dict) else {}


def _flipped_cases(old_rows: list[dict], new_rows: list[dict]) -> list[dict[str, object]]:
    """Return shared case/repeat pairs with changed pass flags or outcomes."""
    old = {(row["case_id"], row["repeat"]): row for row in old_rows}
    new = {(row["case_id"], row["repeat"]): row for row in new_rows}
    flips = []
    for case_id, repeat in sorted(old.keys() & new.keys()):
        old_row, new_row = old[(case_id, repeat)], new[(case_id, repeat)]
        old_actual, new_actual = _decode(old_row["actual"]), _decode(new_row["actual"])
        old_outcome = old_actual.get("outcome", old_actual.get("decision", bool(old_row["passed"])))
        new_outcome = new_actual.get("outcome", new_actual.get("decision", bool(new_row["passed"])))
        if bool(old_row["passed"]) != bool(new_row["passed"]) or old_outcome != new_outcome:
            flips.append(
                {
                    "case_id": case_id,
                    "repeat": repeat,
                    "baseline": old_outcome,
                    "candidate": new_outcome,
                }
            )
    return flips


def _number(value: object) -> bool:
    """Check whether a summary field can be compared numerically."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


st.title("Compare evaluation runs")
runs = list_eval_runs(limit=500)
if len(runs) < 2:
    st.info("Save at least two evaluation runs to compare them.")
else:
    run_by_id = {run["eval_run_id"]: run for run in runs}
    options = list(run_by_id)
    first_id = st.selectbox("Baseline run", options, format_func=lambda key: _label(run_by_id[key]))
    first_run = run_by_id[first_id]
    candidates = [
        run["eval_run_id"]
        for run in runs
        if run["layer"] == first_run["layer"] and run["eval_run_id"] != first_id
    ]
    if not candidates:
        st.info("Choose a layer with two or more saved runs.")
    else:
        second_id = st.selectbox(
            "Candidate run", candidates, format_func=lambda key: _label(run_by_id[key])
        )
        old_metrics = _summary(run_by_id[first_id])
        new_metrics = _summary(run_by_id[second_id])
        metric_rows = [
            {
                "metric": name,
                "baseline": old_metrics[name],
                "candidate": new_metrics[name],
                "delta": new_metrics[name] - old_metrics[name],
            }
            for name in sorted(old_metrics.keys() & new_metrics.keys())
            if _number(old_metrics[name]) and _number(new_metrics[name])
        ]
        st.subheader(f"Metric changes · {first_run['layer']}")
        if metric_rows:
            st.dataframe(pd.DataFrame(metric_rows), use_container_width=True, hide_index=True)
        else:
            st.info("These runs have no shared numeric summary metrics.")
        flips = _flipped_cases(list_eval_results(first_id), list_eval_results(second_id))
        st.subheader("Flipped cases")
        if flips:
            st.dataframe(pd.DataFrame(flips), use_container_width=True, hide_index=True)
        else:
            st.success("No shared case outcomes changed.")
