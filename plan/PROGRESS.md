# Progress

Tick a task only after `make check` passes. Details for each task are in `phases/`. Add session notes at the bottom.

## Phase 0: Skeleton

- [x] **P0.1** Package skeleton and pyproject
- [x] **P0.2** Makefile with make check
- [x] **P0.3** settings.py and models.py
- [x] **P0.4** CI workflow, README and docs stubs

## Phase 1: Deterministic core (no model, no network)

- [x] **P1.1** Diff parser
- [x] **P1.2** Secret redactor
- [x] **P1.3** Rule scanner
- [x] **P1.4** Verifier
- [x] **P1.5** Merge and dedupe
- [x] **P1.6** Risk score and judge
- [x] **P1.7** Example diffs and review CLI

## Phase 2: Storage and tracing

- [x] **P2.1** SQLite storage
- [x] **P2.2** Tracing
- [x] **P2.3** Wire review CLI to storage, add runs commands
- [x] **P2.4** Reconstruction, privacy and concurrency tests

## Phase 3: Golden dataset v0.1 (template-based, no model needed)

- [x] **P3.1** Three sample apps with tests
- [x] **P3.2** Template seeders for 12 security categories
- [x] **P3.3** Mechanical validators
- [x] **P3.4** Mutation-verified bug cases
- [x] **P3.5** Hard negatives, presumed clean, test gaps
- [x] **P3.6** Injection wrappers, variants, verifier attacks
- [x] **P3.7** Build, split, canaries, manifest, stats

## Phase 4: Evaluation harness, component evals, dashboard base

- [x] **P4.1** Stats, matching and result storage
- [x] **P4.2** Thresholds and eval runner CLI
- [x] **P4.3** L1 component suites
- [x] **P4.4** Dashboard base pages and smoke tests
- [x] **P4.5** Static HTML report command

## Phase 5: Model client, context, first agent, agent evals

- [x] **P5.1** LLM client with modes and scripted fake
- [x] **P5.2** Context collector
- [x] **P5.3** Prompt loader and security prompt
- [x] **P5.4** Security reviewer agent
- [x] **P5.5** Security reviewer eval suite
- [x] **P5.6** LLM-assisted dataset growth (v0.2)

## Phase 6: The agent team, the graph, pipeline evals, ablations

- [x] **P6.1** Correctness and test reviewers
- [x] **P6.2** Skeptic agent
- [x] **P6.3** Reporter
- [x] **P6.4** LangGraph pipeline with ablation variants
- [x] **P6.5** Agent and pipeline eval suites
- [x] **P6.6** Ablation study and write-up
- [x] **P6.7** Dashboard pages for pipeline, ablations, cost

## Phase 7: GitHub integration, human approval, resilience

- [x] **P7.1** GitHub client
- [x] **P7.2** Human gate and commands
- [x] **P7.3** review-pr command
- [x] **P7.4** Polling watch mode
- [x] **P7.5** Webhook server
- [x] **P7.6** Graph integration and fault tests
- [x] **P7.7** Threat model and run-it docs

## Phase 8: Regression gates, robustness, consistency, judge calibration

- [x] **P8.1** Compare tool and baseline save
- [x] **P8.2** Regression gate with self-test
- [x] **P8.3** Robustness suites
- [x] **P8.4** Consistency suite
- [x] **P8.5** Judge calibration scaffolding
- [x] **P8.6** CI tiers and nightly workflow
- [x] **P8.7** Dashboard pages for layers, compare, consistency, judge
- [x] **P8.8** Save first baseline

## Phase 9: Dashboard completion, monitoring, documentation, final report

- [x] **P9.1** Live runs page
- [x] **P9.2** Monitoring helpers
- [ ] **P9.3** Documentation
- [ ] **P9.4** README with real results
- [ ] **P9.5** Code-quality pass
- [ ] **P9.6** Final report

## Session notes

2026-11-15: Completed the Phase 0 skeleton: Python 3.11 package layout, typed settings/models, Makefile and CI, and verified with `make check` under the Python 3.11 toolchain. Next session should resume with the first Phase 1 task: P1.1 Diff parser.
2026-11-15: Completed Phase 1 deterministic core: diff parsing, redaction, rule-based scanning, finding verification, dedupe/id assignment, risk scoring, and CLI review behavior. Verified with `make check` under Python 3.11; 69 tests passed.
2026-11-15: Completed Phase 2 storage and tracing: SQLite WAL-backed persistence, run/event/finding models, run listing/show commands, privacy-safe diff hashing, and concurrency-safe writes. Verified with `make check` under Python 3.11; 73 tests passed.
2026-11-15: Completed P3.1 with three MIT-licensed sample applications and 49 focused app tests. Verified all apps meet the 300–600 Python-line plan and `make check` passes on Python 3.11; 122 tests passed. Next: P3.2 template seeders for the 12 security categories.
2026-11-15: Completed P3.2 with four parseable, quote-verified diff templates for each of the 12 security categories. Verified with `make check` under Python 3.11; 130 tests passed. Next: P3.3 mechanical case validators.
2026-11-15: Completed P3.3 with text-only unified-diff application, syntax/location/quote checks, and Bandit/rule-scanner agreement where supported. Verified with `make check` under Python 3.11; 137 tests passed. Next: P3.4 mutation-verified correctness cases.
2026-11-15: Completed P3.4 with 12 AST-generated correctness mutations (two per category), each retained only after its copied sample app's tests failed. Added regression sentinels for the mutations. Verified with `make check` under Python 3.11; 146 tests passed. Next: P3.5 hard negatives, presumed-clean cases and test gaps.
2026-11-15: Completed P3.5 with 20 safe hard negatives, 30 presumed-clean diffs (12 docs, 6 refactors, 12 tested features), and 10 test-gap examples spanning missing, weakened and removed tests plus covered changes. Verified patch evidence, static-tool behavior and isolated sample suites with `make check` under Python 3.11; 150 tests passed. Next: P3.6 injection wrappers, variants and verifier attacks.
2026-11-15: Completed P3.6 with 12 prompt-injection wrappers across code, README and PR metadata, label-preserving comment/reformat/rename/reorder variants, and four rejected verifier attacks per seeded finding. Verified metamorphic findings and exact rejection reasons with `make check` under Python 3.11; 153 tests passed. Next: P3.7 dataset build, splits, canaries, manifest and stats.
2026-11-15: Completed P3.7 with deterministic build/validate/stats commands, SHA-256 split assignment, content-hash manifest, 15 canaries, deduplicated representation variants, and 356 validated cases. Phase verification passed: all planned source counts, `validate` reported no errors, stats reported 212 dev / 144 test and 15 canaries; `make check` passed on Python 3.11 (157 tests). Next: P4.1 evaluation stats, matching and result storage.
2026-11-16: Completed P4.1 with Wilson intervals, small-sample summaries, deterministic paired bootstrap, one-to-one finding matching and unsafe-pass summaries. Suite and case outcomes persist atomically with Git code version, prompt/model metadata and dataset version. `make check` passed on Python 3.11; 171 tests passed. Next: P4.2 thresholds and eval runner CLI.
2026-11-16: Completed P4.2 with starting metric targets, component bars, threshold validation, explicit suite registration, and `python -m evals.run` arguments for layer/split/repeats/cases/mode. Suite results persist with bar outcomes; a missing metric fails its bar. `make check` passed on Python 3.11; 180 tests passed. Next: P4.3 L1 component suites.
2026-11-16: Completed P4.3 with 50 diff parser cases, 150 secret/redactor snippets, v0.1 pattern cases, 240 verifier cases, risk/judge properties and truth table, plus webhook signature and replay checks. `python -m evals.run --layer components --split test` saved a passing result; bars were all met (parser 1.0, secret recall 1.0, placeholder FP 0.0, redaction 1.0, verifier false acceptance/rejection 0.0, judge accuracy 1.0, webhook 1.0). `make check` passed on Python 3.11; 188 tests passed. Next: P4.4 dashboard base pages and smoke tests.
2026-11-16: Completed P4.4 with read-only SQLite dashboard queries, overview/case explorer/dataset pages, cached query results, append-only review logging, a synthetic sample database, and smoke tests on populated and empty databases. Dashboard tests passed (8); `make check` passed on Python 3.11 (196 tests). Next: P4.5 static HTML report command.
2026-11-16: Completed Phase 4: threshold-gated eval runner, all L1 component suites, base dashboard pages, append-only review logging, and static HTML report. Phase verification passed: `python -m evals.run --layer components` saved a passing run with 704 case outcomes; `pytest tests/dashboard` passed (8); `make check` passed on Python 3.11 (200 tests). Generated `evals/results/report.html` from the saved component run. Next: P5.1 LLM client with modes and scripted fake.

2026-11-16: Completed P5.1 with live/record/replay/off modes, SHA-256 request cache, tolerant JSON parsing, Pydantic validation and one repair retry, timeout handling, tracing, and ScriptedLLM coverage. Focused client tests passed (11); make check passed on Python 3.11 (211 tests). No credentials were needed. Next: P5.2 context collector.


2026-11-16: Completed P5.2 with an AST-based collector for callers, test references, sibling functions and fixture-backed CI status; unknown CI is missing. Context blocks are capped at 40 blocks, 1,600 characters each and 12,000 total. Added known-call-graph component cases and path traversal checks. make check passed on Python 3.11 (216 tests). Next: P5.3 security reviewer prompt.


2026-11-16: Completed P5.3 with the versioned security reviewer prompt covering all 12 security categories, untrusted diff/context delimiters, exact quote and evidence requirements, output schema, and empty-list behavior. Verified prompt rendering; make check passed on Python 3.11 (217 tests). Next: P5.4 security reviewer agent.


2026-11-16: Completed P5.4 with a state-based security reviewer that renders the versioned prompt, validates returned Finding objects and marks model/validation failures as incomplete. Scripted tests cover a valid finding, malformed output with exactly one retry then failure, and a complete empty result. make check passed on Python 3.11 (220 tests). Next: P5.5 security reviewer evaluation.


2026-11-16: Completed P5.5 with an agent-only dev-split suite measuring per-category recall, precision, localization, quote validity, severity agreement, hard-negative and presumed-clean false-positive rates, and completion. Results persist through the eval harness. With no LLM credentials, the documented scanner-backed stub ran as reviewer_mode=stub; the required replay command passed and saved 54 cases (precision 1.0, localization 1.0, quote validity 1.0, hard-negative FP 0.0; per-category recall stored). make check passed on Python 3.11 (221 tests). Next: P5.6 LLM-assisted dataset growth.


2026-11-16: Completed P5.6 with seed_issue.v1 generation, exact-diff evidence validation, an independently routed cross-check model, and redacted disagreement review-queue entries. Added build --version v0.2 --llm; the no-credentials command printed a clear skip and exited 0 without creating v0.2. Scripted generation/cross-check and no-write tests passed; make check passed on Python 3.11 (225 tests). Live LLM growth was not run because credentials are unavailable.


2026-11-16: Completed P6.1 with correctness and test reviewers, category/source-restricted Pydantic response schemas, versioned prompts, bounded diff/context instructions, and visible incomplete status on failures. Scripted tests cover valid, out-of-scope retry failure, and empty findings. make check passed on Python 3.11 (229 tests). Next: P6.2 skeptic agent.


2026-11-16: Completed P6.2 with a skeptical verdict agent that receives one finding, its exact containing hunk, and only its cited context evidence. The orchestration helper filters out rule findings and low-severity findings, and marks missing hunks or invalid verdicts incomplete. Scripted tests confirm rule findings are never sent. make check passed on Python 3.11 (232 tests). Next: P6.3 reporter.


2026-11-16: Completed P6.3 with deterministic markdown comments containing decision/reasons, verified finding details, exact file/line citations, finding count, and dismissal commands. A faithfulness checker enforces one-to-one citations and the verified count; model-authored fake citations/counts are sanitized. Tests cover normal, empty, and tampered reports. make check passed on Python 3.11 (235 tests). Next: P6.4 graph and review CLI integration.

2026-11-16: Completed P6.4 with the LangGraph pipeline, parallel reviewers, append-reduced findings, retries/timeouts with visible incomplete status, SQLite checkpoints, and five ablation variants. The review CLI now invokes the graph and reports its decision. Graph tests cover conditional paths, empty diffs, agent failures and each variant. Manual review of examples/flawed_shell.diff returned needs_human with the command-injection finding. make check passed on Python 3.11 (244 tests). Next: P6.5 agent and pipeline eval suites.

2026-11-16: Completed P6.5 with scripted contract evaluations for correctness/test reviewers, skeptic retention/refutation, reporter faithfulness and format retry reliability, plus an L4 suite that runs the actual graph and reports confusion, unsafe-pass, over-block/escalation, finding quality, latency, stub cost/tokens and source/category/difficulty/diff-size slices. The 7 agent contract bars passed. A 6-case pipeline stub run had zero unsafe passes and 100% over-escalation because CI is missing in the offline fixture context. make check passed on Python 3.11 (246 tests). Next: P6.6 ablation study.

2026-11-16: Completed P6.6 with all six graph variants run on 212 dev cases, paired bootstrap intervals (1,000 resamples, seed 42), SQLite-persisted per-variant case results, and the measured report in docs/evaluation.md. Stub results show single_agent matches full on finding recall (0.451), precision (0.687), and unsafe-pass (0); no_rules loses 0.389 recall points. CI is missing, so all variants safely return needs_human; these are not live-model quality claims. Pipeline and ablation replay commands both completed. make check passed on Python 3.11 (247 tests). Next: P6.7 dashboard pages.

2026-11-16: Completed P6.7 with pipeline confusion/slice and unsafe-pass views, an ablation comparison page, and cost/latency summaries with per-agent recorded-call aggregates. Added read-only cached queries and AppTest coverage of all pages on populated and empty databases. make check passed on Python 3.11 (247 tests). Phase 6 verification completed: review CLI on examples/flawed_shell.diff produced a decision; full pipeline and ablation replay runs saved 212-case results. Next: P7.1 GitHub integration.

2026-11-16: Completed P7.1 with an injectable httpx GitHub REST client for PR metadata/diff/files, combined status and check runs, one marked MergeGuard comment, commit statuses, issue comments and open PRs. Added pagination, bounded backoff for server/rate-limit responses, recorded HTTP fixtures, and a credential-gated read-only live test. make check passed on Python 3.11 (250 passed, 1 skipped). The live test skipped because GitHub credentials are not configured; recorded in BLOCKERS.md. Next: P7.2 human gate and commands.

2026-11-16: Completed P7.2 with strict approve/override/dismiss parsing, .mergeguard.yml approver checks, stale head SHA rejection, action-specific rules, feedback/event persistence, and a LangGraph interrupt that resumes from the SQLite checkpoint. Approve/override updates the final decision; dismiss removes an active finding and re-runs the judge. Tests cover parser errors, unauthorized users, stale SHAs, override and dismiss rules, and a checkpointed approve/resume. make check passed on Python 3.11 (254 passed, 1 skipped). Next: P7.3 review-pr command.

2026-11-16: Completed P7.3 with `mergeguard review-pr owner/repo#N`: it fetches PR metadata, diff, changed files and CI; runs the checkpointed review graph; stores findings/run state; and publishes the commit status plus the single MergeGuard report comment. Tests verify target parsing and pass/success and needs_human/pending publication mappings; API tests cover block/failure. make check passed on Python 3.11 (258 passed, 1 skipped). Next: P7.4 polling watch mode.

2026-11-16: Completed P7.4 with `mergeguard watch owner/repo --shadow --interval N`, open-PR polling, and exact repo/PR/head idempotency. Waiting runs inspect comments from approvers and resume their saved checkpoint; shadow mode records without posting. A dismissed finding that still needs review re-interrupts instead of losing the waiting state. Tests cover new/unchanged heads, changed-head processing, shadow no-post behavior, and command-driven resume. make check passed on Python 3.11 (260 passed, 1 skipped). Next: P7.5 webhook server.

2026-11-16: Completed P7.5 with POST /webhook raw-body HMAC authentication, constant-time signature comparison, delivery-id replay protection, supported-event filtering, and background dispatch for PR and issue-comment events. `mergeguard serve` now launches Uvicorn with configurable bind options. ASGI tests cover valid, invalid, missing and replayed signatures/deliveries, unsupported events, malformed JSON, and missing delivery IDs. make check passed on Python 3.11 (263 passed, 1 skipped). Next: P7.6 graph integration and fault tests.

2026-11-16: Completed P7.6 with scripted integration coverage for pass/interrupt routing, malformed model output, timeout, and one reviewer failing; fixed reviewer transport runtime failures to mark runs incomplete. Added tests for checkpointed dismiss/resume, stale and unauthorized approvals, watch idempotency, GitHub 5xx, SQLite lock, model timeout, and concurrent PR threads. `python -m evals.run --layer integration` passed all five cases; `make check` passed on Python 3.11 (269 passed, 1 skipped). Next: P7.7 threat model and run-it docs.
2026-11-16: Completed P7.7 with the threat model, trust boundaries, token permissions, residual risks, operator checklist, and README instructions for local, PR, polling, and webhook use. Phase 7 verification: `python -m evals.run --layer integration` passed (5/5); `make check` passed (269 passed, 1 skipped). Live GitHub checks remain credential-gated as recorded in BLOCKERS.md.
2026-11-16: Completed P8.1 with saved-run comparisons, paired bootstrap intervals for shared numeric case metrics, flipped-case lists, Markdown output, and `baseline save` snapshots of the newest run per layer. Added CLI commands and tests for comparison, baseline JSON, and active baseline metadata. `make check` passed on Python 3.11 (274 passed, 1 skipped). Next: P8.2 regression gate and self-test.
2026-11-16: Completed P8.2 with regression gates for unsafe passes, verifier acceptance, schema validity, paired-interval recall/false-positive/agreement drops, L1 bars, and cost/latency warnings. Added the passing-baseline/degraded-stub self-test as the regression eval layer. `python -m evals.run --layer regression` passed; `make check` passed on Python 3.11 (280 passed, 1 skipped). Next: P8.3 robustness suites.
2026-11-16: Completed P8.3 with fake and credential-gated live robustness modes. The L5 fake suite ran 12 injection wrappers against unwrapped diffs and five odd inputs; it reported zero decision changes, zero visible marker leaks, zero crashes, and marked empty/oversized diffs incomplete. Oversized diffs now fail closed before model calls. `python -m evals.run --layer robustness` passed all bars; `make check` passed on Python 3.11 (282 passed, 1 skipped). Next: P8.4 consistency suite.
2026-11-16: Completed P8.4 with a five-repeat minimum consistency suite on the test split, reporting decision agreement, pairwise finding Jaccard, flip rate, and per-case flaky tags. `python -m evals.run --layer consistency --cases 2` passed (agreement 1.0, Jaccard 1.0); `make check` passed on Python 3.11 (283 passed, 1 skipped). Next: P8.5 judge calibration scaffolding.
2026-11-16: Completed P8.5 with the judge rubric and JSONL template, Cohen kappa and tie-aware Spearman helpers, complete-row loading, and 40-sample calibration threshold. Evaluation suite and per-case judge metrics now carry calibrated/uncalibrated markers. `make check` passed on Python 3.11 (287 passed, 1 skipped). Next: P8.6 CI tiers and nightly workflow.
2026-11-16: Completed P8.6 with a pull-request tier for make check, L1, L3, fake L5, L2/L4 smoke sets, and baseline regression comparison. Added saved-run gate CLI and a clear self-test fallback until the first baseline is committed. Added credential-gated nightly live L2/L4/L5 runs at three repeats and weekly five-repeat L6 plus ablations. Workflow YAML parsed; `make check` passed on Python 3.11 (290 passed, 1 skipped). Next: P8.7 dashboard pages.
2026-11-16: Completed P8.7 with read-only dashboard pages for layer summaries, run comparison and flipped cases, consistency/flaky cases, and judge calibration coverage/agreement. AppTest passed on empty and populated databases, including populated comparison and flaky details. `make check` passed on Python 3.11 (291 passed, 1 skipped). Next: P8.8 save first baseline.
2026-11-16: Completed P8.8 by saving and committing the first baseline from full replay runs for components, integration, robustness, agent security, other agents, pipeline, and regression (925 cases total). The saved PR-tier comparison passed; it reported two non-failing missing paired-interval warnings. Regression eval and gate self-test passed, including the deliberate degradation rejection. `make check` passed on Python 3.11 (291 passed, 1 skipped). Next: P9.1 live runs dashboard.
2026-11-16: Completed P9.1 with the live-runs page showing review decisions, findings, event trace, human feedback, last-hour operational alerts, and pipeline metric drift over 14 days versus the saved baseline. Added cached read-only queries and populated/empty database AppTest coverage. `make check` passed on Python 3.11 (292 passed, 1 skipped). Next: P9.2 monitoring helpers.
2026-11-16: Completed P9.2 with `mergeguard shadow-report`, a persisted summary of shadow-mode runs, dismissal rates by finding category, and approvals/overrides after blocked runs. Tests cover summary content and CLI JSON output. `make check` passed on Python 3.11 (294 passed, 1 skipped). Next: P9.3 documentation.
