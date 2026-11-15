# Phase 4: Evaluation harness, component evals, dashboard base

Goal: run evaluations, store results, see them in a browser. Read `04-evaluation.md` and `06-dashboard.md`.
Depends on: Phases 2 and 3.

## Tasks

- [ ] **P4.1** `evals/stats.py` (Wilson interval, paired bootstrap with fixed seed, small-sample rule), `evals/matching.py` (finding match rule, recall, precision, unsafe-pass rate), `evals/results.py` (`SuiteResult`, save to `eval_runs` and `eval_results`, record code version from git, prompt versions, dataset version). Unit tests for every function.
- [ ] **P4.2** `evals/thresholds.yml` with every L1 bar and the starting targets from `04-evaluation.md`, and `evals/run.py` with the CLI `python -m evals.run --layer <name> [--split] [--repeats] [--cases] [--mode]`. A suite passes only if all its bars pass; exit code 1 otherwise.
- [ ] **P4.3** L1 suites in `evals/suites/components.py`: diff parser, secret scanner, pattern scanner, redactor, verifier, risk scorer, judge truth table, webhook signature (add a signature helper in `api.py` if it does not exist yet, tested). Context collector suite is added in Phase 5.
- [ ] **P4.4** Dashboard base in `dashboard/`: `app.py`, `queries.py`, pages `1_Overview.py`, `4_Case_Explorer.py`, `9_Dataset.py` (including the review queue writing to `review_log.jsonl`). `tests/make_sample_db.py` builds `tests/fixtures/sample.db`. `tests/dashboard/test_pages.py` runs each page with `streamlit.testing.v1.AppTest` on the sample DB and on an empty DB.
- [ ] **P4.5** `mergeguard eval report` command writing `evals/results/report.html` (static summary of the latest eval run per layer).

## Verify

`python -m evals.run --layer components` exits 0 and stores a run; `pytest tests/dashboard`; `make check`.

## Done when

L1 results exist in SQLite and every dashboard page in this phase runs on sample and empty databases.
