# 06. Evaluation dashboard

Streamlit app in `dashboard/` reading the SQLite file through a read-only connection. Run with `streamlit run dashboard/app.py`.

## Pages (one file per page in `dashboard/pages/`)

| File | What it shows | Source |
|---|---|---|
| `1_Overview.py` | Latest gate status (pass or fail), metric cards with change versus baseline, trend lines | eval_runs |
| `2_Layers.py` | One tab per layer with its metrics and bars (green or red) | eval_runs.summary, thresholds.yml |
| `3_Pipeline.py` | Decision confusion matrix, recall by category, red list of unsafe-passes and over-blocks | eval_results |
| `4_Case_Explorer.py` | Filters by source, category, split, tier, outcome. Case detail: diff with expected and actual findings, each agent's output, verifier rejections, skeptic notes, timeline with tokens, cost and latency | eval_results, events |
| `5_Compare_Runs.py` | Pick two runs: metric deltas with intervals, flipped cases, regressions-only filter | two eval_runs |
| `6_Consistency.py` | Per-case stability across repeats, flaky cases | eval_results |
| `7_Ablations.py` | One row per variant with recall, precision, cost, latency and a verdict | ablation runs |
| `8_Cost_Latency.py` | Per-node waterfall, p50 and p95, cost per PR per agent | events |
| `9_Dataset.py` | Browse generated cases and counts by source, category, split, and tier | datasets, manifest |
| `10_Live_Runs.py` | Real PR reviews: decision, findings, trace, feedback, drift charts, alert banners | runs, events, feedback |

Build order: Overview, Case Explorer, Compare Runs first; the rest as each layer comes online. Dashboard pages use read-only access to saved runs and dataset files.

## Implementation notes

- Put all SQL in `dashboard/queries.py`, so pages contain only layout.
- Use pandas and plotly. Cache queries with `st.cache_data` and a short TTL.
- Show an empty-state message on every page when its data does not exist yet.
- Provide `tests/fixtures/sample.db` (built by `tests/make_sample_db.py`) and smoke-test every page with `streamlit.testing.v1.AppTest`: the page must run without exception on the sample DB and on an empty DB.
- `mergeguard eval report` writes `evals/results/report.html`, a static summary of the latest run.
