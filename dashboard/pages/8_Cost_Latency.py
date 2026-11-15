# Summarizes measured review latency and recorded per-agent model call cost.

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.queries import latest_eval_run, list_llm_event_summaries

st.title("Cost and latency")
pipeline = latest_eval_run("pipeline")
ablations = latest_eval_run("ablations")
runs = [item for item in (pipeline, ablations) if item is not None]
if not runs:
    st.info("No pipeline or ablation evaluation is available yet.")
else:
    for run in runs:
        try:
            metrics = json.loads(run["summary"] or "{}")
        except (TypeError, json.JSONDecodeError):
            metrics = {}
        st.subheader(f"{run['layer']} · {metrics.get('reviewer_mode', 'unknown')} mode")
        if run["layer"] == "pipeline":
            st.metric("p50 latency", f"{metrics.get('p50_latency_seconds', 0):.4f} s")
            st.metric("p95 latency", f"{metrics.get('p95_latency_seconds', 0):.4f} s")
            st.metric("Cost per PR", f"${metrics.get('cost_usd_per_pr', 0):.4f}")
            st.caption(f"Tokens per PR: {metrics.get('tokens_per_pr', 'unknown')}")
        else:
            variants = metrics.get("variants", {})
            rows = [
                {
                    "variant": name,
                    "median_latency_seconds": values.get("latency_seconds"),
                    "cost_usd_per_pr": values.get("cost_usd_per_pr"),
                }
                for name, values in variants.items()
            ]
            if rows:
                frame = pd.DataFrame(rows)
                st.plotly_chart(
                    px.bar(frame, x="variant", y="median_latency_seconds"),
                    use_container_width=True,
                )
                st.dataframe(frame, use_container_width=True, hide_index=True)
    events = list_llm_event_summaries()
    st.subheader("Recorded model calls by agent")
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
    else:
        st.info(
            "No live model-call events have been recorded. Stub evaluations have zero model cost."
        )
