# Shows end-to-end graph metrics and labeled unsafe-pass or over-block cases.

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.queries import latest_eval_run, list_eval_results

st.title("Pipeline evaluation")
run = latest_eval_run("pipeline")
if run is None:
    st.info("No pipeline evaluation is available yet. Run python -m evals.run --layer pipeline.")
else:
    try:
        metrics = json.loads(run["summary"] or "{}")
    except (TypeError, json.JSONDecodeError):
        metrics = {}
    st.caption(f"Run {run['eval_run_id']} · {metrics.get('reviewer_mode', 'unknown')} mode")
    columns = st.columns(4)
    columns[0].metric("Unsafe-pass rate", f"{metrics.get('unsafe_pass_rate', 0):.1%}")
    columns[1].metric("Over-block rate", f"{metrics.get('over_block_rate', 0):.1%}")
    columns[2].metric("Finding recall", f"{metrics.get('finding_recall', 0):.1%}")
    columns[3].metric("Precision", f"{metrics.get('precision', 0):.1%}")
    confusion = metrics.get("confusion_matrix", {})
    if confusion:
        st.subheader("Decision confusion matrix")
        frame = pd.DataFrame(confusion).fillna(0).astype(int).rename_axis("Decision")
        st.dataframe(frame, use_container_width=True)
    slices = metrics.get("slices", {}).get("category", {})
    if slices:
        st.subheader("Finding recall by category")
        frame = pd.DataFrame([{"category": name, **values} for name, values in slices.items()])
        st.plotly_chart(px.bar(frame, x="category", y="finding_recall"), use_container_width=True)
    unsafe_passes = []
    over_blocks = []
    for result in list_eval_results(run["eval_run_id"]):
        expected = json.loads(result["expected"] or "{}")
        actual = json.loads(result["actual"] or "{}")
        expected_decision = expected.get("decision", "pass")
        if expected_decision in {"block", "needs_human"} and actual.get("decision") == "pass":
            unsafe_passes.append(result["case_id"])
        if expected_decision == "pass" and actual.get("decision") == "block":
            over_blocks.append(result["case_id"])
    st.subheader("Cases needing attention")
    st.error(f"Unsafe passes: {len(unsafe_passes)}")
    if unsafe_passes:
        st.dataframe(pd.DataFrame({"case_id": unsafe_passes}), hide_index=True)
    st.warning(f"Over-blocks: {len(over_blocks)}")
    if over_blocks:
        st.dataframe(pd.DataFrame({"case_id": over_blocks}), hide_index=True)
