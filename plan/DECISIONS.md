# Decisions

Pre-made defaults. Add new decisions at the bottom (date, decision, reason). Do not reopen the defaults without a concrete failing reason.

| # | Decision | Default |
|---|---|---|
| 1 | Language and version | Python 3.11 |
| 2 | Package layout | `src/mergeguard/`, installable with `pip install -e '.[dev]'`, built with setuptools via pyproject.toml |
| 3 | Orchestration | LangGraph only. No Band, no LangChain agents |
| 4 | Runtime dependencies | langgraph, langgraph-checkpoint-sqlite, pydantic (v2), fastapi, uvicorn, httpx, openai (SDK only, used with a custom base URL), pyyaml, typer, rich, python-dotenv |
| 5 | Dashboard and eval dependencies (extra `eval`) | streamlit, pandas, plotly, numpy, bandit (used only to validate seeded dataset cases) |
| 6 | Dev dependencies (extra `dev`) | pytest, pytest-cov, ruff, black, mypy, types-PyYAML, plus the `eval` extra |
| 7 | Storage | One SQLite file at `data/mergeguard.db` (WAL mode). Also holds LangGraph checkpoints |
| 8 | Background work | FastAPI background tasks. No queue, no Redis |
| 9 | GitHub publishing | Commit status (context `mergeguard`) plus one PR comment, using a fine-grained token. A GitHub App Check Run is out of scope for now |
| 10 | GitHub intake | Polling mode first (`mergeguard watch owner/repo`), webhook mode second. Polling needs no public URL |
| 11 | Model access | OpenAI-compatible Chat Completions through `llm.py`. JSON output parsed and validated with Pydantic, one retry on failure. Do not depend on provider-specific structured-output features |
| 12 | LLM modes | `LLM_MODE` is live, record, replay or off. Tests and CI use replay or a scripted fake. `off` raises an error |
| 13 | Language scope | Python repositories only |
| 14 | Dashboard | Streamlit, read-only SQLite connection |
| 15 | Test runner and CI | pytest; GitHub Actions workflow `ci.yml` runs `make check` and the fast eval tier |
| 16 | Risk threshold | 71 (configurable in `settings.py` and `.mergeguard.yml`) |
| 17 | Agent timeout | 60 seconds per LLM node, one retry with backoff |
| 18 | Dataset base code | Small sample applications written inside this repo under `evals/sample_repos/` (MIT). Real repositories are an optional extension |
| 19 | Hash split | dev if `int(sha256(case_id).hexdigest(), 16) % 100 < 60`, otherwise test |
| 20 | Out of scope | Deploy, auto-merge, multiple languages, user accounts, vector database, Redis |

## Log

2026-11-16 P9.4: Moved Streamlit, pandas, and Plotly into base dependencies so the README quick start's `pip install -e .` includes the dashboard runtime; they remain dashboard runtime dependencies even though originally grouped in the `eval` extra.
