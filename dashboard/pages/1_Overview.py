# Overview of recent saved evaluation runs and their summary metrics.
# The page remains useful when the database has no evaluation history.

import json

import pandas as pd
import streamlit as st

from dashboard.queries import list_eval_runs

st.title("Evaluation overview")
runs = list_eval_runs()
if not runs:
    st.info("No evaluation runs are available yet.")
else:
    latest = runs[0]
    try:
        metrics = json.loads(latest["summary"] or "{}")
    except (TypeError, json.JSONDecodeError):
        metrics = {}
    st.subheader(f"Latest layer: {latest['layer']}")
    st.caption(
        f"Run {latest['eval_run_id']} · dataset {latest['dataset_version']} · "
        f"code {latest['code_version']}"
    )
    st.metric("Recent runs", len(runs))
    if metrics:
        st.json(metrics)
    st.subheader("Recent runs")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "started_at": run["started_at"],
                    "layer": run["layer"],
                    "dataset": run["dataset_version"],
                    "repeats": run["repeats"],
                    "baseline": bool(run["is_baseline"]),
                }
                for run in runs
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
