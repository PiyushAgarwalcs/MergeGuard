# Compares full-team graph results with each planned ablation.

import json

import pandas as pd
import streamlit as st

from dashboard.queries import latest_eval_run

st.title("Ablation study")
run = latest_eval_run("ablations")
if run is None:
    st.info(
        "No ablation run is available yet. Run python -m evals.run --layer ablations --split dev."
    )
else:
    try:
        metrics = json.loads(run["summary"] or "{}")
    except (TypeError, json.JSONDecodeError):
        metrics = {}
    st.caption(f"Run {run['eval_run_id']} · {metrics.get('reviewer_mode', 'unknown')} mode")
    variants = metrics.get("variants", {})
    if variants:
        rows = [{"variant": name, **values} for name, values in variants.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        comparison = metrics.get("paired_differences_vs_full", {})
        if comparison:
            st.subheader("Paired differences versus full design")
            rows = [
                {"variant": variant, "metric": metric, **interval}
                for variant, values in comparison.items()
                for metric, interval in values.items()
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if metrics.get("single_agent_matches_team_on_quality_and_safety"):
            st.success(
                "The single agent matched the full team on recall, precision, and unsafe-pass rate in this run."
            )
        else:
            st.info(
                "The single agent did not match the full team on every reported quality and safety metric."
            )
        if metrics.get("reviewer_mode") == "stub":
            st.warning(
                "This is a scripted stub comparison; it does not establish live-model quality."
            )
    else:
        st.info("The saved run has no variant results.")
