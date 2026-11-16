# Phase 7: GitHub integration, human approval, resilience

Goal: review real pull requests safely. Read `01-decisions-and-scope.md` (human commands, invariants) and `07-security-and-code-standards.md`.
Depends on: Phase 6.

## Tasks

- [x] **P7.1** `github.py` with `httpx`: get PR, get diff, list changed files, read CI status (combined status and check runs), post or update the single MergeGuard comment, set the `mergeguard` commit status, list PR comments, list open PRs. Retries with backoff on 5xx and rate limits. Tests against recorded HTTP fixtures in `tests/fixtures/github/`. Live tests marked `@pytest.mark.live`.
- [x] **P7.2** `checks/human_gate.py` using a LangGraph interrupt, plus a command parser for `/mergeguard approve`, `/mergeguard override <reason>`, `/mergeguard dismiss F-N <reason>`. Rules: only users listed in the repo's `.mergeguard.yml` approvers; approvals bound to the head SHA; stale approvals rejected; override requires a reason; every action stored in `feedback` and `events`. Resume the run through the checkpointer. Tests for all rules.
- [x] **P7.3** `mergeguard review-pr owner/repo#N`: fetch a PR, run the graph, publish the status and comment. Status mapping: pass is success, needs_human is pending, block is failure.
- [x] **P7.4** `mergeguard watch owner/repo [--shadow] [--interval 60]`: poll open PRs, process each new head SHA once (idempotency on repo, PR, SHA), poll comments for commands and resume waiting runs. `--shadow` records but posts nothing.
- [x] **P7.5** `api.py` and `mergeguard serve`: FastAPI `/webhook` (HMAC check on raw body, constant-time compare, delivery id stored in `deliveries`, only pull_request and issue_comment events, background task) and `/health`. Tests: valid, invalid, missing and replayed signatures; duplicate delivery processed once.
- [x] **P7.6** L3 suite `evals/suites/graph_integration.py` and tests: interrupt and resume paths, stale and unauthorized approvals, idempotency, crash and resume from the checkpoint, fault injection (model timeout, malformed JSON, GitHub 5xx, SQLite lock, one reviewer failing), two PRs at once. Each fault ends in `needs_human` with `complete=False`, never a crash and never `pass`.
- [x] **P7.7** `docs/threat-model.md` filled in from `07-security-and-code-standards.md`, and a short "Run it on your repository" section in the README.

## Verify

`make check`; `python -m evals.run --layer integration`; if `MERGEGUARD_GITHUB_TOKEN` and `TEST_REPO` are set, `pytest -m live` and `mergeguard review-pr $TEST_REPO#1`.

## Done when

All offline tests pass; live GitHub tests pass or are listed in `BLOCKERS.md`.
