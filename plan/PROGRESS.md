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
- [ ] **P3.5** Hard negatives, presumed clean, test gaps
- [ ] **P3.6** Injection wrappers, variants, verifier attacks
- [ ] **P3.7** Build, split, canaries, manifest, stats

## Phase 4: Evaluation harness, component evals, dashboard base

- [ ] **P4.1** Stats, matching and result storage
- [ ] **P4.2** Thresholds and eval runner CLI
- [ ] **P4.3** L1 component suites
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
