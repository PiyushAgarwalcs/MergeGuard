# 08. Configuration and credentials

## Environment variables

| Variable | Needed from | Purpose |
|---|---|---|
| `LLM_BASE_URL`, `LLM_API_KEY` | phase 4 (live), phase 3 (optional) | any OpenAI-compatible API |
| `REVIEWER_MODEL` | phase 4 | the three reviewers |
| `SKEPTIC_MODEL`, `JUDGE_MODEL` | phase 5 | should be a different model family from the reviewers |
| `GENERATOR_MODEL` | phase 3 (optional) | dataset seeding and cross-check |
| `LLM_MODE` | always | live, record, replay, off. Default `replay` in tests and CI |
| `MERGEGUARD_GITHUB_TOKEN`, `TEST_REPO` | phase 7 | fine-grained token for a throwaway test repo |
| `MERGEGUARD_WEBHOOK_SECRET` | optional | webhook mode only |
| `DATABASE_PATH` | always | default `data/mergeguard.db` |
| `PRIVACY_MODE` | optional | store hashes instead of diffs |

`settings.py` reads the environment (and `.env` through python-dotenv) and exposes typed values. Missing credentials must never crash import or `make check`.

## Where the human puts them

- **Copilot cloud agent:** repository Settings, Environments, environment named `copilot`: add secrets for keys and tokens, variables for model names and the base URL. Add the LLM API host to the agent firewall allowlist in repository settings.
- **Local agent mode (VS Code):** a `.env` file at the repository root (git-ignored).

## What to do when a credential is missing

| Missing | Do this |
|---|---|
| LLM key | Use `ScriptedLLM` and `replay` mode. Build everything. Mark live agent evals as blocked in `BLOCKERS.md`. Build dataset v0.1 with the template seeders, skipping the cross-check |
| Several model names | Use one model for everything, mark skeptic and judge independence as a deviation in `DECISIONS.md` |
| GitHub token | Implement `github.py` against recorded HTTP fixtures (`tests/fixtures/github/`). Mark live GitHub tests as blocked |
| Webhook secret | Implement and test signature verification with a test secret; skip live webhook runs |

Live tests are marked with `@pytest.mark.live` and are skipped unless the needed variables are set.

## Prices (`config/prices.yml`)

Per model: `input_per_1k`, `output_per_1k`. Unknown models default to 0, and the dashboard shows cost as "unpriced".
