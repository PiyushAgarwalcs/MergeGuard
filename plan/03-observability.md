# 03. Observability

Every number on the dashboard comes from the SQLite file. Every run must be reconstructable from it.

## API (`tracing.py`)

```python
with tracing.span(run_id, 'security_reviewer'):   # records start, end, duration, errors
    ...
tracing.record_llm_call(run_id, node, model, prompt_version, tokens_in, tokens_out, latency_ms, output)
tracing.record(run_id, node, kind, payload)       # rejection, verdict, decision, error, human
```

Cost is computed from `config/prices.yml` (price per 1,000 input and output tokens per model, default 0 if unknown). Logs are structured, one line per event, always carrying `run_id`, `repo`, `pr_number`, `head_sha`.

## Tables (create in `storage.py` with a migration function; WAL mode; busy timeout 5000 ms)

```sql
CREATE TABLE runs (
  run_id TEXT PRIMARY KEY, repo TEXT, pr_number INT, head_sha TEXT,
  started_at TEXT, finished_at TEXT, status TEXT, outcome TEXT,
  code_version TEXT, prompt_versions TEXT, model_config TEXT,
  total_cost_usd REAL, total_ms INT);
CREATE TABLE events (
  id INTEGER PRIMARY KEY, run_id TEXT, ts TEXT, node TEXT,
  kind TEXT,  -- span, llm_call, rejection, verdict, decision, error, human
  model TEXT, prompt_version TEXT, tokens_in INT, tokens_out INT,
  cost_usd REAL, latency_ms INT, payload TEXT);
CREATE TABLE findings (
  run_id TEXT, finding_id TEXT, source TEXT, category TEXT, severity TEXT,
  file TEXT, line_start INT, line_end INT, quote TEXT,
  verified INT, skeptic_verdict TEXT, status TEXT);  -- status: shown, dismissed, rejected
CREATE TABLE feedback (run_id TEXT, finding_id TEXT, action TEXT, by_user TEXT, reason TEXT, ts TEXT);
CREATE TABLE deliveries (delivery_id TEXT PRIMARY KEY, received_at TEXT);   -- idempotency
CREATE TABLE eval_runs (
  eval_run_id TEXT PRIMARY KEY, started_at TEXT, layer TEXT, dataset_version TEXT,
  code_version TEXT, prompt_versions TEXT, model_config TEXT,
  repeats INT, is_baseline INT, summary TEXT);   -- summary is JSON of metrics
CREATE TABLE eval_results (
  eval_run_id TEXT, case_id TEXT, repeat INT, passed INT,
  expected TEXT, actual TEXT, metrics TEXT, run_id TEXT);   -- run_id links to the full trace
```

Every eval case result links to a normal run trace through `run_id`.

## What gets recorded

Node start and end with duration; every LLM call (model, prompt version, tokens, cost, latency, raw output; hash only when `PRIVACY_MODE=true`); verifier rejections with reason; skeptic verdicts; the decision with reasons; errors, retries, timeouts and fallbacks; human actions.

## Metrics the dashboard must be able to compute

Verifier rejection rate per agent; skeptic overturn rate; dismissal rate per category; share of runs ending `needs_human`; LLM timeout, retry and JSON-failure rates; partial-review rate; p50 and p95 latency per node and per PR; cost and tokens per PR and per agent.

## Privacy

Secrets found in a diff are redacted (`checks/redact.py`) before any model call and before anything is stored. With `PRIVACY_MODE=true` store diff hashes instead of diff text. Logs never include raw diffs or secrets.

## Alerts (version 1)

The dashboard shows a red banner and the service logs a warning when, over the last hour, the JSON-failure rate is above 5 percent, LLM timeouts are above 10 percent, or any run ended with an unhandled error.
