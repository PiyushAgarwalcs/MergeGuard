# MergeGuard final report

## What was built

MergeGuard is an installable Python 3.11 pull-request review and merge-gate application. It parses and redacts diffs, scans deterministically, runs security/correctness/test reviewers and a skeptic through LangGraph, verifies model findings against changed-line evidence, and applies a deterministic judge. The result is `pass`, `block`, or `needs_human`; incomplete reviews and missing CI fail closed. Local review, GitHub review/polling/webhooks, SHA-bound human approval, SQLite persistence/checkpoints, structured traces, and feedback are implemented.

The repository includes a versioned seeded dataset, evaluation layers, comparison and regression gates, robustness and consistency suites, judge-calibration scaffolding, CI/nightly workflows, static reporting, and a read-only Streamlit dashboard for evaluations and live operational runs. Operator guidance is in `README.md`, `docs/how-it-works.md`, `docs/evaluation.md`, and `docs/threat-model.md`.

## Latest recorded evaluation

The latest full pipeline run is saved in `data/mergeguard.db` (eval run `a3c55079-941c-4d07-9256-6290e2314bbb`), using dataset `v0.1`, test split, 144 cases, and reviewer mode `stub`. The evaluation is a deterministic offline measurement; it is not live-model quality evidence.

| Metric | Result |
|---|---:|
| Finding recall | 0.508 |
| Precision | 0.629 |
| False findings per clean case | 0.043 (1 / 23 hard-negative and presumed-clean cases) |
| Unsafe-pass rate | 0 / 39 must-catch cases (0.000) |
| Decisions | 144 / 144 `needs_human`; over-escalation 1.000 |
| p95 latency | 0.0834 s |
| Cost per PR | $0.00 (stub mode) |
| Repeated-run decision agreement | not yet measured on a full saved consistency run |
| Judge calibration | uncalibrated; 0 / 40 human-scored samples |

The 100% escalation rate reflects unavailable CI in the offline fixture context. No live model calls or GitHub credentials were available. The first baseline snapshot is committed at `evals/baselines/main.json`; it contains the full replay layer runs and per-case results. The latest `make eval-fast` run passed components and integration suites.

The saved six-variant ablation on 212 development cases reports `single_agent` matching the full design on stub recall (0.451), precision (0.687), and unsafe-pass rate (0). Removing rules reduced recall by 0.389. Scripted reviewers returned empty findings and the rule scanner drove detections, so this does not establish that a live single agent matches the team.

## Deviations and limitations

- LLM credentials were unavailable. Dataset cross-checks were skipped where permitted; live reviewer, nightly, and live robustness results were not produced. Replay and scripted stubs were used. See `plan/BLOCKERS.md`.
- GitHub credentials and a test repository were unavailable. Live GitHub verification was skipped; the client and flows were tested with recorded fixtures and fakes.
- Full five-repeat consistency measurements and the 40-sample judge calibration have not been collected. The calibration status stays explicitly `uncalibrated`.
- `.env.example` and package metadata were adjusted so the documented `pip install -e .` quick start includes the dashboard and evaluation modules. Dashboard runtime packages are base dependencies.
- The threat model records a remaining privacy limitation: the diff itself is sent to an authorized live model provider; trace redaction and privacy mode do not prevent that transmission.
- MergeGuard reviews Python pull requests, does not execute pull-request code, and does not auto-merge. Static and model-assisted review can miss defects or report false findings.

## Open blockers

- Configure an approved OpenAI-compatible provider endpoint and key to run live agent, pipeline, robustness, and nightly evaluations.
- Configure a scoped GitHub token and disposable test repository to run the credential-gated live GitHub test.
- Collect at least 40 complete human/judge pairs, then review calibration agreement and bias before relying on judge-based metrics.
- Run the full five-repeat consistency suite at production settings and record its saved agreement, Jaccard, flip-rate, and flaky-case outputs.

## Suggested next steps

1. Add provider credentials through the CI secret store and run nightly L2/L4/L5 suites; keep repository data-sharing policy in view.
2. Add a disposable GitHub test repository and run read-only integration checks before enabling publishing.
3. Collect human-scored calibration samples and full consistency results.
4. Replace the stub baseline only with a reviewed, explained update using `python -m evals.run baseline save`.
5. Treat shadow dismissal rates and dashboard drift as operator signals; do not automate tuning from feedback.
