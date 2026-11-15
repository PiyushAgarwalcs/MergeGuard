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
- [ ] **P4.4** Dashboard base pages and smoke tests
- [ ] **P4.5** Static HTML report command

## Phase 5: Model client, context, first agent, agent evals

- [ ] **P5.1** LLM client with modes and scripted fake
- [ ] **P5.2** Context collector
- [ ] **P5.3** Prompt loader and security prompt
- [ ] **P5.4** Security reviewer agent
- [ ] **P5.5** Security reviewer eval suite
- [ ] **P5.6** LLM-assisted dataset growth (v0.2)

## Phase 6: The agent team, the graph, pipeline evals, ablations

- [ ] **P6.1** Correctness and test reviewers
- [ ] **P6.2** Skeptic agent
- [ ] **P6.3** Reporter
- [ ] **P6.4** LangGraph pipeline with ablation variants
- [ ] **P6.5** Agent and pipeline eval suites
- [ ] **P6.6** Ablation study and write-up
- [ ] **P6.7** Dashboard pages for pipeline, ablations, cost

## Phase 7: GitHub integration, human approval, resilience

- [ ] **P7.1** GitHub client
- [ ] **P7.2** Human gate and commands
- [ ] **P7.3** review-pr command
- [ ] **P7.4** Polling watch mode
- [ ] **P7.5** Webhook server
- [ ] **P7.6** Graph integration and fault tests
- [ ] **P7.7** Threat model and run-it docs

## Phase 8: Regression gates, robustness, consistency, judge calibration

- [ ] **P8.1** Compare tool and baseline save
- [ ] **P8.2** Regression gate with self-test
- [ ] **P8.3** Robustness suites
- [ ] **P8.4** Consistency suite
- [ ] **P8.5** Judge calibration scaffolding
- [ ] **P8.6** CI tiers and nightly workflow
- [ ] **P8.7** Dashboard pages for layers, compare, consistency, judge
- [ ] **P8.8** Save first baseline

## Phase 9: Dashboard completion, monitoring, documentation, final report

- [ ] **P9.1** Live runs page
- [ ] **P9.2** Monitoring helpers
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
