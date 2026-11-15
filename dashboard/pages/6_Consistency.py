# Shows agreement, finding stability, flips and flaky cases from the latest run.
# The page reads saved run summaries and their case rows without writing to SQLite.

import json

import pandas as pd
import streamlit as st

from dashboard.queries import latest_eval_run, list_eval_results


def _decode(value: str | None) -> dict:
    """Decode JSON text into a mapping for safe dashboard display."""
    try:
        result = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return result if isinstance(result, dict) else {}


def _summary(run: dict) -> dict:
    """Decode the saved metric summary, returning an empty mapping on bad JSON."""
    return _decode(run.get("summary"))


st.title("Consistency evaluation")
run = latest_eval_run("consistency")
if run is None:
    st.info("No consistency run is available yet. Run python -m evals.run --layer consistency.")
else:
    metrics = _summary(run)
    st.caption(
        f"Run {run['eval_run_id']} · {metrics.get('repeats_per_case', run['repeats'])} repeats per case"
    )
    columns = st.columns(4)
    columns[0].metric("Decision agreement", f"{metrics.get('decision_agreement', 0):.1%}")
    columns[1].metric("Finding Jaccard", f"{metrics.get('finding_jaccard', 0):.3f}")
    columns[2].metric("Flip rate", f"{metrics.get('flip_rate', 0):.1%}")
    columns[3].metric("Flaky cases", len(metrics.get("flaky_case_ids", [])))
    flaky_ids = metrics.get("flaky_case_ids", [])
    if flaky_ids:
        st.warning("Cases below the decision-agreement bar are tagged flaky.")
        st.dataframe(pd.DataFrame({"flaky_case_id": flaky_ids}), hide_index=True)
    rows = []
    for result in list_eval_results(run["eval_run_id"]):
        case_metrics = _decode(result.get("metrics"))
        if case_metrics.get("flaky"):
            rows.append(
                {
                    "case_id": result["case_id"],
                    "repeat": result["repeat"],
                    "decision_agreement": case_metrics.get("decision_agreement"),
                    "finding_jaccard": case_metrics.get("finding_jaccard"),
                }
            )
    if rows:
        st.subheader("Flaky case repeats")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
