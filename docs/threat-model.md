# MergeGuard threat model

## Scope and assets

MergeGuard reviews Python pull requests by reading GitHub metadata, diffs, changed paths, and CI results. It does not check out or execute pull request code. The assets to protect are the GitHub token, webhook secret, model credentials, source and diff content, approval records, findings, and the SQLite review database.

The pull request author, diff, title, description, filenames, comments, webhook body, model response, and CI result are untrusted inputs. The local operator controls configuration, credentials, the database file, and the approver allow-list in the target repository's `.mergeguard.yml`.

## Trust boundaries and controls

| Boundary or threat | Control in MergeGuard | Residual risk |
|---|---|---|
| Attacker-controlled diff attempts prompt injection | Reviewer prompts delimit the diff as data and state that it contains no instructions. Reviewers have no tools. Findings require schema validation and mechanical quote, location, file, category, and evidence checks. Only verified findings reach the decision. | A model can still miss a defect or return a misleading but verifiable concern. Review output is not a substitute for human review. |
| Model tries to suppress a deterministic finding | Rule findings are kept in the decision inputs and are not sent to the skeptic. Model findings cannot lower a rule finding or the deterministic judge decision. | Rule scanners have limited coverage and can produce false positives. |
| Malformed model output, timeout, outage, or reviewer exception | Responses are Pydantic-validated with one repair attempt. Failed reviewer calls mark the run incomplete. The judge routes incomplete runs to `needs_human`; no reviewer failure produces `pass`. | `needs_human` requires a human to inspect and resolve the run. |
| Forged webhook or replayed delivery | The webhook validates an HMAC-SHA256 signature over the raw request body using constant-time comparison. Delivery IDs are recorded and duplicates are ignored. Unsupported event types are not dispatched. | The webhook secret must remain private. A compromised secret allows forged requests until it is rotated. Restrict network access to the webhook endpoint where practical. |
| Unauthorized or stale human decision | Only usernames listed in `.mergeguard.yml` approvers may act. Approval payloads are checked against the current head SHA. Commands and reasons are stored in the review event and feedback records. | Repository administrators can change the allow-list; protect that file with normal code review and branch rules. |
| Excessive GitHub access | Use a fine-grained token restricted to the target repositories. Required permissions are Pull requests: read/write, Commit statuses: read/write, Contents: read, Checks: read, Metadata: read, and Issues: read/write for PR comments. Model reviewers are not passed the GitHub client or token. | The token exists in the MergeGuard process environment and can be exposed by a compromise of that host or its dependencies. Do not use a personal broad-scope token. |
| PR code execution | MergeGuard reads patches and CI results from GitHub; it never runs PR code. | CI is an external signal. Missing or failing CI routes to `needs_human`. |
| Large or hostile diffs | Diff size is capped by `MAX_DIFF_LINES`; truncation marks the review incomplete. Paths and context collection are bounded. | A truncated review cannot establish that omitted code is safe. It requires human review. |
| Sensitive content in model calls, traces, or storage | The trace layer redacts recognized secret patterns, and `PRIVACY_MODE=true` stores hashes for diff and model output trace fields. SQLite uses WAL and a busy timeout. | Redaction is pattern-based and is not a guarantee that all secrets are removed. Reviewer prompts currently receive the review diff itself; operators should only enable live model access for repositories whose code they are permitted to send to that provider. Protect the SQLite file and backups with host filesystem permissions. |
| GitHub API or SQLite failure | API retries are bounded. Review command failures return a visible incomplete `needs_human` result; database writes use SQLite transactions and busy timeout. | If the database is unavailable, persistence may itself fail; repair storage and rerun the review before treating any status as current. |

## Decision safety

The judge uses the fixed decision order in `plan/01-decisions-and-scope.md`: verified critical findings block; incomplete reviews and missing or failing CI need a human; verified high findings or high risk need a human; only a complete review with passing CI and no blocking condition can pass. Human approval is bound to one commit SHA, so a new push requires a new review.

The published GitHub status is `success` for pass, `pending` for needs_human, and `failure` for block. Configure branch protection to require the `mergeguard` status if it is being used as a merge gate. MergeGuard does not enable auto-merge.

## Monitoring and feedback

The Live Runs dashboard reads operational events and feedback from SQLite. It flags elevated JSON-failure and timeout rates and unhandled errors over the last hour, and compares recent pipeline evaluation metrics with the saved baseline over a rolling 14-day window. `mergeguard shadow-report` summarizes shadow reviews and dismissal feedback by category, and lists approvals or overrides recorded after a block. These signals are for operator review: feedback does not automatically change thresholds, prompts, or model behavior. The alert rates depend on events being recorded and should be treated as monitoring aids rather than proof that a service is healthy.

## Operator checklist

- Store credentials in environment secrets or a local ignored `.env`; never commit them.
- Use a fine-grained GitHub token with access only to the repositories being reviewed.
- Set an explicit approver list in each target repository's `.mergeguard.yml` and protect changes to it.
- Use `LLM_MODE=replay` or scripted fakes for offline development. Use `live` only after confirming provider data handling is acceptable for the repository.
- Set `PRIVACY_MODE=true` when traces should avoid retaining diff and model output text; keep in mind that this does not prevent content from being sent to the configured model.
- Keep the SQLite database and backups private. Apply operating-system access controls and a retention policy appropriate to the source code.
- Treat `needs_human`, incomplete runs, missing CI, and unavailable statuses as unresolved. Do not merge based on an absent or stale result.

## Verification

Offline tests exercise signature validation and replay protection, prompt injection cases, secret redaction, verifier attacks, stale and unauthorized approvals, duplicate PR/head processing, model and GitHub failures, SQLite locking, and checkpoint resume. The credential-gated live GitHub test is skipped when `MERGEGUARD_GITHUB_TOKEN` or `TEST_REPO` is absent.
