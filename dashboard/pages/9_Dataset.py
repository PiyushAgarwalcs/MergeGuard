# Read-only dataset browser showing counts and generated case details.

import streamlit as st

from dashboard.queries import (
    dataset_counts,
    load_dataset_cases,
)

st.title("Dataset")
version = st.text_input("Dataset version", value="v0.1")
cases = load_dataset_cases(version)
if not cases:
    st.info(f"No dataset cases are available for {version}.")
else:
    counts = dataset_counts(version)
    st.metric("Total cases", counts["total"])
    left, middle, right = st.columns(3)
    left.caption("By source")
    left.json(counts["source"])
    middle.caption("By category")
    middle.json(counts["category"])
    right.caption("By split and tier")
    right.json({"split": counts["split"], "tier": counts["tier"]})
    selected_id = st.selectbox("Dataset case", [str(case["id"]) for case in cases])
    selected = next(case for case in cases if case["id"] == selected_id)
    st.code(selected["diff"], language="diff")
    st.json(selected["findings"])
