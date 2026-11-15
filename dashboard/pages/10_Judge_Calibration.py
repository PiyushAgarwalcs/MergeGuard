# Displays judge calibration coverage and agreement with human scores.
# Metrics remain visibly uncalibrated until the required paired sample count exists.

import json

import pandas as pd
import streamlit as st

from dashboard.queries import list_eval_runs
from evals.judges.calibration import (
    CALIBRATION_SAMPLE_TARGET,
    cohen_kappa,
    load_calibration_samples,
    spearman_rank,
)

st.title("Judge calibration")
try:
    samples = load_calibration_samples()
except (OSError, TypeError, ValueError) as error:
    samples = []
    st.error(f"Calibration data could not be read: {error}")
count = len(samples)
calibrated = count >= CALIBRATION_SAMPLE_TARGET
st.metric("Calibration samples", f"{count} / {CALIBRATION_SAMPLE_TARGET}")
if calibrated:
    human_scores = [sample.human_score for sample in samples]
    judge_scores = [sample.judge_score for sample in samples]
    kappa = cohen_kappa(
        [str(score) for score in human_scores], [str(score) for score in judge_scores]
    )
    st.metric("Cohen's kappa", f"{kappa:.3f}" if kappa is not None else "undefined")
    correlation = spearman_rank(human_scores, judge_scores)
    st.metric(
        "Spearman rank correlation",
        f"{correlation:.3f}" if correlation is not None else "undefined",
    )
    st.success(
        "Judge-based metrics have calibration data; review rubric and bias checks before relying on them."
    )
else:
    st.warning(
        "Judge-based metrics are uncalibrated until 40 complete paired samples are recorded."
    )

st.subheader("Calibration status on saved evaluations")
runs = list_eval_runs(limit=500)
rows = []
for run in runs:
    try:
        summary = json.loads(run["summary"] or "{}")
    except (TypeError, json.JSONDecodeError):
        summary = {}
    calibration = summary.get("judge_calibration", {})
    if calibration or any("judge" in key.casefold() for key in summary):
        rows.append(
            {
                "layer": run["layer"],
                "run_id": run["eval_run_id"],
                "status": calibration.get("status", "uncalibrated"),
                "sample_count": calibration.get("sample_count", count),
            }
        )
if rows:
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No judge-based metrics are present in saved runs.")
if samples:
    st.subheader("Paired ratings")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "sample_id": sample.sample_id,
                    "case_id": sample.case_id,
                    "human_score": sample.human_score,
                    "judge_score": sample.judge_score,
                    "judge_model": sample.judge_model,
                    "rubric_version": sample.rubric_version,
                }
                for sample in samples
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
