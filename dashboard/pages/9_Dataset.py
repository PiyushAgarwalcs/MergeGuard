# Dataset counts, case details, and append-only review decisions.
# Human actions go to review_log.jsonl and never mutate generated labels.

import streamlit as st

from dashboard.queries import (
    append_review_action,
    dataset_counts,
    load_dataset_cases,
    load_review_log,
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
    selected_id = st.selectbox("Review case", [str(case["id"]) for case in cases])
    selected = next(case for case in cases if case["id"] == selected_id)
    st.code(selected["diff"], language="diff")
    st.json(selected["findings"])
    with st.form("review-action"):
        action = st.selectbox("Action", ["accept", "reject", "edit"])
        reviewer = st.text_input("Reviewer", value="local-reviewer")
        reason = st.text_input("Reason")
        submitted = st.form_submit_button("Save review action")
        if submitted:
            try:
                append_review_action(version, selected_id, action, reviewer, reason)
            except (OSError, ValueError) as error:
                st.error(str(error))
            else:
                st.success("Review action appended.")
    review_log = load_review_log(version)
    st.subheader("Review log")
    if review_log:
        st.json(review_log)
    else:
        st.info("No review actions have been recorded for this dataset.")
