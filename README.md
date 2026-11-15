# MergeGuard

MergeGuard is a LangGraph pull request review and merge gate for Python repositories. It combines deterministic security rules with separate security, correctness, and test reviewers. It verifies findings against the diff, asks a skeptic to challenge model findings, and applies a deterministic judge. Reviews, events, and LangGraph checkpoints are stored in SQLite.

The published commit status is `success` for `pass`, `pending` for `needs_human`, and `failure` for `block`. A needs-human decision can be resolved by a listed approver using a PR comment. MergeGuard does not merge pull requests or execute their code.

## Install and check

Use Python 3.11. From the repository root:

```bash
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -e '.[dev]'
make check
```

Review a local unified diff without GitHub access:

```bash
mergeguard review examples/flawed_shell.diff
```

This stores a run in `data/mergeguard.db` and prints its decision. Without a working model configuration, the reviewers fail closed and the result is `needs_human`; deterministic rule findings still run.

## Run it on your repository

1. Install MergeGuard in its own environment and configure credentials in an ignored `.env` file. Start with `.env.example`. For live reviews, set `LLM_MODE=live`, an OpenAI-compatible `LLM_BASE_URL` and `LLM_API_KEY`, plus `REVIEWER_MODEL` and `SKEPTIC_MODEL`. Keep model credentials out of commits and logs.
2. In the target repository, add `.mergeguard.yml` with an explicit list of trusted approvers. `.mergeguard.yml.example` shows the supported policy keys. Protect this file with your repository's normal branch rules.
3. Create a fine-grained GitHub token scoped to the target repository. Grant Pull requests read/write, Commit statuses read/write, Contents read, Checks read, Metadata read, and Issues read/write (for PR comments). Put it in `MERGEGUARD_GITHUB_TOKEN`.
4. From the target repository's working directory, run one review:

   ```bash
   mergeguard review-pr owner/repository#123
   ```

   MergeGuard reads the PR diff and CI result, saves a checkpoint and publishes one status and one report comment. Re-run after a new push to review the new head SHA.

5. For polling, run:

   ```bash
   mergeguard watch owner/repository
   ```

   Polling processes each PR head once and checks comments for approver commands. Add `--shadow` to save reviews without publishing status or comments; adjust the polling interval with `--interval 60`.

6. To accept webhooks instead, set `MERGEGUARD_WEBHOOK_SECRET` to the secret configured in GitHub, then run `mergeguard serve --host 0.0.0.0 --port 8000` behind an HTTPS endpoint that forwards GitHub webhook requests to `/webhook`. Configure pull request and issue comment events. The service also provides `/health`.

Configure branch protection to require the `mergeguard` commit status before merging. MergeGuard never enables auto-merge. Approver comments are `/mergeguard approve`, `/mergeguard override <reason>` for a block, or `/mergeguard dismiss F-N <reason>` for an active finding. Actions are limited to usernames in `.mergeguard.yml` and tied to the reviewed head SHA.

## Configuration and data

Important settings are documented in `.env.example`: model access, GitHub access, `DATABASE_PATH`, `PRIVACY_MODE`, `MAX_DIFF_LINES`, and `AGENT_TIMEOUT_SECONDS`. Missing CI, an incomplete diff, an unavailable model, or a reviewer failure leads to `needs_human`. `LLM_MODE=replay` expects a recorded response cache; tests use scripted model responses and do not need credentials.

The SQLite database contains review runs, findings, events, approvals, feedback, evaluations, and checkpoints. Keep the database and its backups private. `PRIVACY_MODE=true` hashes diff and model-output trace fields, but does not stop review content from being sent to a configured model. See [the threat model](docs/threat-model.md) before enabling live review or webhooks.

## Evaluations and dashboard

Run the graph integration suite or the full test/check suite:

```bash
python -m evals.run --layer integration
make check
```

Generate a static report from saved evaluations with `mergeguard eval report`. Run the local dashboard with `make dashboard`; it reads the SQLite database and is read-only.

For architecture notes, see [How it works](docs/how-it-works.md), [Evaluation](docs/evaluation.md), and [Threat model](docs/threat-model.md).
