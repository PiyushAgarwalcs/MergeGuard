# Dashboard landing page for MergeGuard evaluation runs and dataset review.
# All displayed evaluation data comes from the local read-only SQLite store.

import sys
from pathlib import Path

# Ensure project root and src/ are in sys.path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))

import streamlit as st

from dashboard.queries import list_eval_runs

st.set_page_config(page_title="MergeGuard", page_icon="🛡️", layout="wide")
st.title("MergeGuard evaluation dashboard")
st.caption("Review component quality, saved evaluation outcomes, and dataset cases.")

runs = list_eval_runs(limit=1)
if runs:
    latest = runs[0]
    st.subheader("Latest evaluation")
    st.write(f"Layer: **{latest['layer']}** · Dataset: **{latest['dataset_version']}**")
    st.caption(f"Run {latest['eval_run_id']} · {latest['started_at']}")
else:
    st.info(
        "No evaluation runs are saved yet. Run `python -m evals.run --layer components` to add one."
    )

st.markdown("Use the pages in the sidebar to inspect evaluation results and dataset cases.")
