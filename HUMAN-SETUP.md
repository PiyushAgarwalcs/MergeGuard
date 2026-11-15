# Setup (the only part you do by hand)

## A. Put the files in a repo

1. Create a new empty GitHub repository (private is fine).
2. Copy the contents of this folder into its root, including the hidden `.github` folder, then commit and push.

## B. Add the settings (one by one)

You need two LLM models from different families, one API key, and (later) one GitHub token. The build runs without any of them, so you can do step C first and add these when ready.

| # | Name | Secret? | What it is | Example |
|---|---|---|---|---|
| 1 | `LLM_BASE_URL` | no | The OpenAI-compatible URL of your LLM provider (see its docs) | `https://api.example.com/v1` |
| 2 | `LLM_API_KEY` | **yes** | Your provider's API key | |
| 3 | `REVIEWER_MODEL` | no | Model id for the three reviewers, exactly as your provider lists it | |
| 4 | `GENERATOR_MODEL` | no | Model for building the test dataset. Can be the same as #3 | |
| 5 | `SKEPTIC_MODEL` | no | Model for the skeptic. Should be a different family from #3 | |
| 6 | `JUDGE_MODEL` | no | Model for judging. Can be the same as #5 | |
| 7 | `MERGEGUARD_GITHUB_TOKEN` | **yes** | Fine-grained GitHub token for a throwaway test repo. Needed only from phase 7 | |
| 8 | `TEST_REPO` | no | The throwaway repo as `owner/name`, with at least one open pull request | |
| 9 | `MERGEGUARD_WEBHOOK_SECRET` | **yes** | Optional. Only for webhook mode. Skip it | |

Creating the GitHub token (#7): GitHub, Settings, Developer settings, Personal access tokens, Fine-grained tokens, Generate new token. Under Repository access choose only the test repo. Repository permissions: Pull requests Read and write, Commit statuses Read and write, Contents Read, Checks Read, Issues Read and write, Metadata Read.

Where to enter them:

- **Copilot cloud agent:** repository Settings, Environments, New environment named `copilot`. Add the secrets (#2, #7) under Environment secrets and the rest under Environment variables. Then in repository settings add your LLM provider's host name (for example `api.example.com`, no `https://`) to the Copilot agent firewall allowlist.
- **VS Code agent mode:** copy `.env.example` to `.env` and fill it in. Never commit `.env`.

Do not paste secrets into chats, issues, pull requests or any file in the repository.

## C. Start Copilot

Tell Copilot (an issue assigned to Copilot, or the agent chat):

> Read AGENTS.md and plan/README.md, then implement the project by following plan/PROGRESS.md. Do not ask me questions; follow the rules in the plan.

If a session ends early, send the same message again. It resumes from the first unchecked task in `plan/PROGRESS.md`.
