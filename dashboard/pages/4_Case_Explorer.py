# Filters dataset cases and shows their evidence and saved evaluation outputs.
# A missing dataset or evaluation run produces a clear empty state.

import json

import streamlit as st

from dashboard.queries import list_eval_results, list_eval_runs, load_dataset_cases

st.title("Case explorer")
version = st.text_input("Dataset version", value="v0.1")
cases = load_dataset_cases(version)
if not cases:
    st.info(f"No cases are available for dataset {version}.")
else:
    sources = ["All"] + sorted({str(case["source"]) for case in cases})
    categories = ["All"] + sorted({str(case["category"]) for case in cases})
    splits = ["All"] + sorted({str(case["split"]) for case in cases})
    tiers = ["All"] + sorted({str(case["tier"]) for case in cases})
    outcomes = ["All"] + sorted({str(case["expected_decision"]) for case in cases})
    source = st.selectbox("Source", sources)
    category = st.selectbox("Category", categories)
    split = st.selectbox("Split", splits)
    tier = st.selectbox("Tier", tiers)
    outcome = st.selectbox("Expected outcome", outcomes)
    filtered = [
        case
        for case in cases
        if (source == "All" or case["source"] == source)
        and (category == "All" or case["category"] == category)
        and (split == "All" or case["split"] == split)
        and (tier == "All" or case["tier"] == tier)
        and (outcome == "All" or case["expected_decision"] == outcome)
    ]
    st.write(f"{len(filtered)} matching cases")
    if filtered:
        selected_id = st.selectbox("Case", [str(case["id"]) for case in filtered])
        selected = next(case for case in filtered if case["id"] == selected_id)
        st.subheader(selected_id)
        st.code(selected["diff"], language="diff")
        st.markdown("**Expected findings**")
        st.json(selected["findings"])
        st.markdown("**Provenance**")
        st.json(selected["provenance"])
        runs = list_eval_runs()
        if runs:
            run_id = st.selectbox("Saved evaluation run", [run["eval_run_id"] for run in runs])
            result = next(
                (row for row in list_eval_results(run_id) if row["case_id"] == selected_id), None
            )
            if result:
                st.markdown("**Evaluation result**")
                st.json(
                    {
                        "passed": bool(result["passed"]),
                        "expected": json.loads(result["expected"] or "{}"),
                        "actual": json.loads(result["actual"] or "{}"),
                    }
                )
            else:
                st.info("This case has no result in the selected run.")
