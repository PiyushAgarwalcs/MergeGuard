# 04. Evaluation

Goal: answer with numbers whether each part works, whether the whole pipeline works, whether a change made things worse, and whether multi-agent beats a single agent.

## Principles

1. Ground truth comes from how a case was built, never from a model's opinion (`05-golden-dataset.md`).
2. Test the smallest part that can fail. Use the cheapest check that works. Use an LLM judge only where nothing mechanical exists.
3. Every metric has a baseline and a threshold (`evals/thresholds.yml`).
4. Tune on the dev split only. Report from the test split.
5. Every result stores code version, prompt versions, model config, dataset version and seed.
6. Every result is written to SQLite (`eval_runs`, `eval_results`).

## Implementation contract (`evals/`)

- Each suite is a module in `evals/suites/` exposing `run(config) -> SuiteResult` (metrics dict, per-case results with expected, actual, passed, run_id).
- `python -m evals.run --layer <name> [--split dev|test] [--repeats N] [--cases N] [--mode live|replay]` runs a suite and saves it.
- `evals/thresholds.yml` holds every bar. A suite passes only if all its bars pass.
- `evals/compare.py` compares two eval runs: metric deltas with confidence intervals and flipped cases.
- Statistics (`evals/stats.py`): Wilson interval for proportions; paired bootstrap (1,000 resamples, fixed seed) for differences. Below 30 cases in a slice, report raw counts and no percentage claims.
- Matching rule: a predicted finding matches an expected one if file and category agree and line ranges overlap within 3 lines. Recall = matched expected / expected. Precision = matched predicted / predicted shown. Unsafe-pass rate = must_catch PRs with outcome `pass` / must_catch PRs.

## Layers

| Layer | Tests | LLM | When |
|---|---|---|---|
| L0 unit | pure functions | no | every commit (`pytest`) |
| L1 components | scanners, verifier, risk, judge, context, redactor, diff parser, webhook signature | no | every commit |
| L2 agents | each LLM agent alone, context fixed | yes | prompt or model change, nightly |
| L3 graph and integration | routing, interrupt and resume, idempotency, crash recovery, fault injection | scripted fake | every commit |
| L4 end-to-end | full pipeline, PR in, decision out | yes | nightly, before release |
| L5 robustness | prompt injection, odd inputs | fake and live | every commit (fake), nightly (live) |
| L6 consistency | same case repeated | yes | nightly or weekly |
| L7 ablations | which design choices matter | yes | milestones |
| L8 regression | compare with baseline, gate CI | both | every pull request |
| L9 online | shadow mode, feedback, drift | live | continuous |
| L10 judge validation | trust in LLM judges | yes | when a judge changes |

## L1 component evals (no model, every commit)

| Part | Data | Bar |
|---|---|---|
| Diff parser | 50 tricky diffs: renames, binary, CRLF, no final newline, unicode, deleted-only | line numbers correct in 100% |
| Secret scanner | about 150 snippets: real-format synthetic keys, high-entropy strings, placeholders, test fixtures | recall at least 95% on real-format keys; false positives on placeholders at most 2% |
| Pattern scanner | seeded snippets per category plus hard negatives | precision and recall reported per category |
| Redactor | diffs containing synthetic secrets | 100% removed before any model call or storage |
| Context collector | fixture repos with a known call graph | callers and covering tests found; size caps respected |
| Verifier | four adversarial sets: fabricated quote, wrong lines, invented evidence id, quote from unchanged context | 100% of fabricated rejected; 0 genuine rejected |
| Risk scorer | labeled risky and safe diffs; property tests | adding a critical never lowers the score; more risky files never lowers it; AUC reported |
| Judge | exhaustive truth table | matches `01-decisions-and-scope.md` in every case; missing input never gives `pass` |
| Webhook signature | valid, invalid, missing, replayed | only valid first-seen deliveries accepted |

## L2 agent evals

Context is pre-built and fixed so only the agent varies.

- security_reviewer: recall by category, precision, localization accuracy (within 3 lines), quote-validity rate, severity agreement, false-positive rate on hard negatives.
- correctness_reviewer: the same on mutation-verified bugs and clean code.
- test_reviewer: accuracy on test-gap cases.
- skeptic: fed true and false findings. Retention of true findings (target at least 95%), refutation rate of false ones, skeptic lift.
- reporter: faithfulness checked mechanically (every file, line and count in the comment maps to a verified finding); clarity scored by a calibrated judge.
- format reliability: schema-valid rate after one retry per agent (target at least 99%).

## L3 graph and integration (scripted fake model)

Every conditional edge is taken at least once. Interrupt and resume: approve, override, dismiss, approval for an old SHA is rejected, approval by a non-approver is rejected. Idempotency: same delivery twice gives one run. Crash recovery: stop between nodes, resume, same decision. Fault injection: model timeout, malformed JSON, GitHub 5xx, SQLite lock, one reviewer failing; each ends in a defined state (`needs_human` with `complete=False`), never a crash and never `pass`. Two PRs at once do not mix state.

## L4 end-to-end metrics

Decision accuracy and confusion matrix; unsafe-pass rate (target 0 on the canary set); over-block rate; over-escalation rate; finding recall, precision, F1, localization, severity agreement; p50 and p95 latency; cost and tokens per PR. Every metric also split by source, category, diff size and difficulty.

## L5 robustness

Injection placements: code comment, docstring, string literal, filename, commit message, PR title, PR body, README change. Goals: say it is safe, ignore the rules, lower a severity, reveal the prompt, invent a finding, request a tool call. Checks: metamorphic (decision identical to the same PR without the injection) and leak (no output contains the attacker marker strings). Odd inputs: empty diff, binary, 5,000-line diff, minified and generated files, vendored directories, non-UTF-8 bytes, right-to-left unicode, very long lines, mixed line endings, rename-only, lockfile-only, submodule bump. Bar: no crash, deterministic fallback, partial flag set when coverage is incomplete.

## L6 consistency

Each case five times at production settings. Decision agreement, finding-set Jaccard, flip rate. Bar: at least 95% decision agreement. Below-bar cases are tagged flaky.

## L7 ablations

Variants: (a) one agent with all checklists in one prompt; (b) three reviewers without skeptic; (c) full design without verifier; (d) without context; (e) without rule_scan. Record recall, precision, unsafe-pass, cost, latency; report differences with bootstrap intervals. Write the outcome to `docs/evaluation.md` including the case where the single agent matches the team.

## L8 regression testing

- **Baseline:** `evals/baselines/main.json` per layer, with metrics and per-case outcomes. Saved with `python -m evals.run baseline save`. Changed only in a pull request that explains why.
- **Pull-request tier (CI, free, deterministic):** L0, L1, L3, fake-model L5, plus L2 and L4 on a 30-case smoke set using recorded model responses (record and replay cache keyed by hash of model, prompt and parameters). Changing a prompt, model or dataset version invalidates the cache and requires a live smoke run.
- **Nightly tier (`.github/workflows/nightly-evals.yml`):** full live L2, L4, live L5 with 3 repeats; weekly L6 with 5 repeats and ablations. Skips itself with a clear message if credentials are missing.
- **Gates that fail the build:** any unsafe-pass on the canary set; any fabricated finding accepted by the verifier; recall down more than 3 points or false-positive rate up more than 2 points beyond the interval; decision agreement down more than 3 points; any L1 bar missed; schema validity under 99%.
- **Warnings (do not fail):** p95 latency or cost per PR up more than 20%.
- **Output:** list of flipped cases (pass to fail, fail to pass) and a markdown summary suitable for a PR comment.
- **Bug-to-test rule:** every later missed detection or false alarm becomes a new dataset case before it is fixed.
- **Proof that the gate works:** a test that deliberately worsens a prompt (or a stub) and asserts that the regression gate fails.

## L9 online

Shadow mode (`mergeguard watch --shadow`): run and record, post nothing. Feedback is stored. Dismissal rate per category is a precision proxy. Drift: rolling 14-day metrics versus baseline, flagged on the dashboard. No automatic tuning on feedback.

## L10 judge score reporting

Use an LLM judge only where no mechanical check exists. Judge-derived scores are informational, marked `not_validated`, and excluded from acceptance gates. Prefer seeded ground truth and mechanical checks for decisions.

## Starting targets (hypotheses; tune after the first real run, record changes in DECISIONS.md)

| Metric | Target |
|---|---|
| Unsafe-pass rate on canary set | 0 |
| Recall on seeded security issues (test split) | at least 80% |
| False findings shown per clean PR | under 0.3 |
| Fabricated findings accepted by verifier | 0 |
| Decision agreement across 5 repeats | at least 95% |
| Schema-valid rate after one retry | at least 99% |
| p95 latency per PR | under 90 s |
| Injection cases that change the decision | 0 |
