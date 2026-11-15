# Copilot instructions

You are building the project described in `plan/`. Read `plan/README.md` first and follow it.

- Python 3.11. LangGraph is the only orchestration framework. No Band, no Redis, no Celery, no Docker requirement. State lives in one SQLite file.
- Plain functions, small files (about 150 lines), descriptive names, type hints, short comments that explain why.
- No clever tricks: no metaclasses, dynamic imports, abstract base classes or stacked decorators.
- Every agent and check takes the state and returns a dict of the fields it changed.
- Only `llm.py` talks to a model, only `github.py` talks to GitHub, only `storage.py` touches SQLite.
- Every LLM finding needs an exact quote from the diff. The verifier drops findings that fail.
- Never ask the human for input. Use `plan/DECISIONS.md` defaults and record new decisions there.
- Run `make check` before finishing any task. Keep the repository green after every commit.
- Never commit secrets. Read them from environment variables only.
