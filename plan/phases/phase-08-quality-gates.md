# Phase 8: Regression gates, robustness, consistency

Goal: any change that makes the system worse fails CI. Read `04-evaluation.md` (L5, L6, L8).
Depends on: Phases 6 and 7.

## Tasks

- [x] **P8.1** `evals/compare.py` and CLI `python -m evals.run compare <runA> <runB>`: metric deltas with intervals and a list of flipped cases; markdown summary suitable for a PR comment. `python -m evals.run baseline save` writes `evals/baselines/main.json`.
- [x] **P8.2** Regression gate in `evals/gates.py` implementing the gates and warnings from `04-evaluation.md`. A test deliberately worsens a stub or prompt and asserts the gate fails.
- [x] **P8.3** L5 suites `evals/suites/robustness.py`: injection suite (metamorphic and leak checks) and odd-input suite, in a fake-model version for every commit and a live version for nightly runs.
- [x] **P8.4** L6 suite `evals/suites/consistency.py` (5 repeats, decision agreement, Jaccard, flip rate, flaky tagging).
- [x] **P8.6** CI: update `.github/workflows/ci.yml` to run `make check` plus the pull-request tier (L0, L1, L3, fake L5, smoke-set L2 and L4 in replay mode, gate comparison against the baseline). Add `.github/workflows/nightly-evals.yml` (live L2, L4, L5 with 3 repeats; weekly L6 and ablations) that skips with a clear message when credentials are missing.
- [x] **P8.7** Dashboard pages `2_Layers.py`, `5_Compare_Runs.py`, `6_Consistency.py` with AppTest smoke tests.
- [x] **P8.8** Save the first baseline (`baseline save`) from the latest full replay or live run and commit it.

## Verify

`make check`; `python -m evals.run --layer regression`; the gate self-test fails on a deliberately worsened input and passes on the baseline.

## Done when

CI runs the pull-request tier green, the nightly workflow exists, and a baseline is committed.
