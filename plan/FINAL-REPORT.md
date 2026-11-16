# MergeGuard final report

## Project status

MergeGuard is an installable Python 3.11 pull-request review and merge-gate application. It parses and redacts diffs, scans deterministically, runs security, correctness, and test reviewers with a skeptic through LangGraph, verifies model findings against changed-line evidence, and applies a deterministic judge. Decisions are `pass`, `block`, or `needs_human`; incomplete reviews and missing CI fail closed.

Local review, GitHub review and polling, webhook handling, SHA-bound approval actions, SQLite persistence and checkpoints, structured traces, feedback, evaluation suites, regression gates, static reporting, and a read-only Streamlit dashboard are implemented. All planned implementation tasks are complete.

## Latest evaluations

The latest saved consistency run is `662d93f2-a1f3-4534-9e9d-da1760e25459`, dataset `v0.1`, test split, live Ollama mode. It evaluated eight evenly spaced cases with five repeats each (40 reviews). The full 144-case test split exceeded the requested two-hour runtime budget, so the run was reduced and is reported as a sample.

| Consistency metric | Result |
|---|---:|
| Cases / repeats | 8 / 5 |
| Decision agreement | 1.000 |
| Finding Jaccard | 0.925 |
| Flip rate | 0.000 |
| Flaky cases | 0 |
| Decision agreement threshold | passed (minimum 0.95) |

The generated report is `evals/results/report.html` (ignored local output).

The saved `v0.1` pipeline baseline is a 144-case deterministic stub evaluation, not live-model quality evidence. It reports finding recall 0.508, precision 0.629, false findings 0.043 per clean case (1 / 23), unsafe-pass 0 / 39, and 144 / 144 `needs_human` decisions because CI is unavailable in the offline fixture context. The saved six-variant ablation on 212 development cases reports stub recall 0.451 for `single_agent` and a 0.389 recall-point loss for `no_rules`.

Judge-derived scores are informational and marked `not_validated`; they are excluded from acceptance gates. Mechanical checks and seeded ground truth drive the quality gates.

## Verification

`make check` passed with Python 3.11 tooling: Ruff 0.17, Black, mypy, and pytest (294 passed, 1 skipped). The `v0.1` dataset validator passed, as did `make eval-fast`, the regression suite, and gate self-test.

## Operational setup

- Configure a live LLM provider in the ignored `.env` file when live review is wanted. Ollama is the local option; Groq is optional.
- Configure a scoped GitHub token and a disposable test repository to run the credential-gated live GitHub checks and enable repository integration.
- Review `README.md`, `docs/how-it-works.md`, `docs/evaluation.md`, and `docs/threat-model.md` before enabling publishing or branch protection.

MergeGuard supports Python pull requests, does not execute pull-request code, and does not auto-merge. Missing CI, incomplete diffs, reviewer failures, and unavailable model responses require human review.
