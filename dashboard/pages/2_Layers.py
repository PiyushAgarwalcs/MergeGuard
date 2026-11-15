# Compares the latest saved metrics across evaluation layers.
# Queries use the read-only dashboard connection and never update run records.

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.queries import list_eval_runs

st.title("Evaluation layers")
runs = list_eval_runs(limit=500)
if not runs:
    st.info("No evaluation runs are available yet.")
else:
    latest_by_layer = {}
    for run in runs:
        latest_by_layer.setdefault(run["layer"], run)
    rows = []
    for layer, run in sorted(latest_by_layer.items()):
        try:
            metrics = json.loads(run["summary"] or "{}")
        except (TypeError, json.JSONDecodeError):
            metrics = {}
        rows.append(
            {
                "layer": layer,
                "run_id": run["eval_run_id"],
                "started_at": run["started_at"],
                "cases": metrics.get("case_count", "—"),
                "thresholds_passed": metrics.get("thresholds_passed", "unknown"),
                "dataset": run["dataset_version"],
            }
        )
    frame = pd.DataFrame(rows)
    st.dataframe(frame, use_container_width=True, hide_index=True)
    numeric_metrics = [
        name
        for name in ("finding_recall", "decision_agreement", "unsafe_pass_rate")
        if any(name in json.loads(run["summary"] or "{}") for run in latest_by_layer.values())
    ]
    if numeric_metrics:
        chart_rows = []
        for layer, run in latest_by_layer.items():
            metrics = json.loads(run["summary"] or "{}")
            chart_rows.extend(
                {"layer": layer, "metric": name, "value": metrics[name]}
                for name in numeric_metrics
                if isinstance(metrics.get(name), (int, float))
            )
        if chart_rows:
            st.plotly_chart(
                px.bar(
                    pd.DataFrame(chart_rows),
                    x="layer",
                    y="value",
                    color="metric",
                    barmode="group",
                ),
                use_container_width=True,
            )
