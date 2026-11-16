# Operational view of saved review runs, traces, feedback, alerts, and recent drift.

from datetime import UTC, datetime, timedelta

import pandas as pd
import streamlit as st

from dashboard.live_queries import (
    list_review_runs,
    live_alerts,
    review_drift,
    review_run_detail,
)

st.title("Live runs")
alerts = live_alerts((datetime.now(UTC) - timedelta(hours=1)).isoformat())
for alert in alerts:
    st.error(alert)
if not alerts:
    st.success("No operational alerts in the last hour.")

drift = review_drift()
st.subheader("14-day drift versus baseline")
if drift["baseline"] is None:
    st.info("No pipeline baseline is saved yet.")
elif drift["recent"] is None:
    st.info("No pipeline evaluation run is available in the last 14 days.")
elif drift["deltas"]:
    st.caption(
        f"Baseline {drift['baseline']['eval_run_id']} · recent {drift['recent']['eval_run_id']}"
    )
    st.dataframe(
        pd.DataFrame(
            [{"metric": key, "delta": value} for key, value in sorted(drift["deltas"].items())]
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("The recent run and baseline have no shared numeric summary metrics.")

runs = list_review_runs()
st.subheader("Review runs")
if not runs:
    st.info("No review runs are available in the configured SQLite database.")
else:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    key: run.get(key)
                    for key in (
                        "run_id",
                        "repo",
                        "pr_number",
                        "head_sha",
                        "started_at",
                        "finished_at",
                        "status",
                        "outcome",
                        "total_ms",
                        "total_cost_usd",
                    )
                }
                for run in runs
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    run_id = st.selectbox("Run details", [run["run_id"] for run in runs])
    selected = next(run for run in runs if run["run_id"] == run_id)
    st.subheader("Decision")
    st.json(
        {
            key: selected.get(key)
            for key in (
                "run_id",
                "repo",
                "pr_number",
                "head_sha",
                "status",
                "outcome",
                "code_version",
                "prompt_versions",
                "model_config",
            )
        }
    )
    detail = review_run_detail(run_id)
    st.subheader("Findings")
    if detail["findings"]:
        st.dataframe(pd.DataFrame(detail["findings"]), use_container_width=True, hide_index=True)
    else:
        st.info("No findings were stored for this run.")
    st.subheader("Trace")
    if detail["events"]:
        st.dataframe(pd.DataFrame(detail["events"]), use_container_width=True, hide_index=True)
    else:
        st.info("No trace events were stored for this run.")
    st.subheader("Human feedback")
    if detail["feedback"]:
        st.dataframe(pd.DataFrame(detail["feedback"]), use_container_width=True, hide_index=True)
    else:
        st.info("No human feedback was recorded for this run.")
