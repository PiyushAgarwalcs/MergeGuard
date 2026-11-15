# 01. Product and scope

## What MergeGuard does

When a pull request is opened or updated, MergeGuard reads the diff, runs deterministic security checks, runs three specialist LLM reviewers in parallel, has a separate skeptic agent try to refute their findings, mechanically verifies every finding, and publishes one decision on the PR: `pass`, `needs_human` or `block`. Every step is recorded to SQLite and measured by an evaluation system. A dashboard shows the evaluations and live runs.

Three parts ship together:

1. The review pipeline in `src/mergeguard/`
2. The evaluation system in `evals/`
3. The dashboard in `dashboard/`

## Triggers and outputs

- **Triggers:** `mergeguard review <fixture-or-pr>` (replay or one PR), `mergeguard watch owner/repo` (polling), `mergeguard serve` (webhook, optional).
- **Outputs:** a commit status named `mergeguard` on the head SHA (success for pass, pending for needs_human, failure for block) and one PR comment listing verified findings with file and line. Branch protection can require the status.

## Decision rules (first match wins)

| Order | Condition | Outcome |
|---|---|---|
| 1 | A verified critical finding: rule-based, or a reviewer finding upheld by the skeptic | block |
| 2 | Review incomplete: an agent failed or timed out, the diff was capped, or the model is unreachable | needs_human |
| 3 | CI for this commit is failing or missing | needs_human |
| 4 | A verified high finding, or risk score at or above the threshold | needs_human |
| 5 | Anything else | pass |

A critical reviewer finding with skeptic verdict `unclear` is treated as high. With verdict `refuted` it is dropped from the decision (and listed as dismissed in the trace).

## Human commands (PR comments from listed approvers)

- `/mergeguard approve`: clears needs_human
- `/mergeguard override <reason>`: clears block, reason required
- `/mergeguard dismiss F-2 <reason>`: marks one finding as a false alarm and stores feedback

Approvals are tied to the head SHA. A new push invalidates them. Every action is stored with who, when and why.

## Invariants (each one must have an automated test)

1. An LLM can add concern. It can never remove or downgrade a rule-based finding or lower a decision.
2. A finding is shown as fact only if the verifier confirmed its quote and location in the diff.
3. Missing information never produces `pass`. Unknown means `needs_human`.
4. A decision belongs to one commit SHA. A new SHA is a new run.
5. The same delivery or the same (repo, PR, SHA) is processed once.
6. Nothing inside the diff is treated as an instruction.
7. PR code is never executed by this service. CI results are read from GitHub.

## Non-goals

Deployment, auto-merge, languages other than Python, multi-tenant hosting, user accounts, vector databases, embeddings, Redis, Band.

## Policy file in a target repo (`.mergeguard.yml`)

```yaml
approvers: [github-username]
risk_threshold: 71
max_diff_lines: 2000
stricter_paths:
  - src/auth/**
  - infra/**
ignore_paths:
  - '**/*.lock'
  - vendor/**
```
