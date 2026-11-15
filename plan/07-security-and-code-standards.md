# 07. Security, reliability and code standards

## Threats and defenses

| Threat | Defense | Tested by |
|---|---|---|
| Forged webhook | HMAC-SHA256 on the raw body, constant-time compare | L1 |
| Duplicate delivery | delivery id or (repo, PR, SHA) stored; second ignored | L3 |
| Prompt injection in the diff | delimited data plus standing instruction; LLM cannot lower a decision; injection suite | L5 |
| Secrets sent to a model or stored | redaction first | L1 |
| Over-privileged token | fine-grained token with only: Pull requests RW, Commit statuses RW, Contents R, Checks R, Metadata R, Issues RW (PR comments). Reviewer agents get no token | threat-model doc |
| Running attacker code | never executed; CI status read from GitHub | design |
| Stale approval | approval stored with SHA; new push invalidates | L3 |
| Unauthorized approval | only users in `.mergeguard.yml` approvers | L3 |
| Huge or hostile diff | size caps, riskiest-hunk selection, `complete=False` | L5 |
| Model outage | timeout, one retry, then `needs_human` | L3 |
| Log leakage | logs never include raw diffs or secrets | L0 |
| SQLite trouble | WAL, busy timeout | L3 |

Every failure ends in a visible state (`needs_human` with a reason), never silence, never `pass`.

## Code standards

1. Plain functions. No base-agent class hierarchies, abstract factories, metaclasses, dynamic imports or stacked decorators.
2. Every step takes the state and returns a dict of the fields it changed.
3. Descriptive names: `find_hardcoded_secrets`, not `process_data`.
4. Type hints everywhere. Pydantic for anything crossing a boundary (model output, GitHub payloads, files).
5. Every file starts with a two-line comment saying what it does. Comments explain why, not what. Every public function has a one-line summary comment or docstring.
6. No magic numbers: thresholds, weights and limits are named in `settings.py`.
7. Files under about 150 lines, functions under about 30, nesting at most two levels. Use early returns.
8. Tests read like examples, one behavior each, named like `test_verifier_rejects_quote_not_in_diff`.
9. Tooling in `make check`: `ruff check .`, `black --check .`, `mypy src`, `pytest -q`.
10. No dead code, no commented-out code, no TODO without a matching line in `BLOCKERS.md`.
11. If a file cannot be explained in a minute, split or simplify it.

An agent file looks like this:

```python
# agents/security_reviewer.py
# Asks a model to review the diff for security problems and returns findings.

from mergeguard import llm
from mergeguard.models import Finding, ReviewState

PROMPT_NAME = 'security_reviewer.v1'


# Every step takes the state and returns only the fields it changed.
def run(state: ReviewState) -> dict:
    prompt = llm.load_prompt(PROMPT_NAME, diff=state['pr'].diff, context=state['context'])
    findings = llm.ask_for_list(prompt, Finding, agent='security_reviewer')
    return {'findings': findings}
```

`graph.py` reads top to bottom: one `add_node` per step in pipeline order, edges, then conditional edges with short named routing functions such as `after_judge`.

## llm.py requirements

`load_prompt(name, **values)`, `ask_for_list(prompt, Model, agent)` and `ask_for_object(...)`. Behavior: build the request, call the OpenAI-compatible API, parse JSON from the reply (tolerate code fences), validate with Pydantic, retry once with the error appended, record every call via `tracing`. Modes by `LLM_MODE`: `live` calls the API; `record` calls and saves to `.cache/llm/<hash>.json`; `replay` reads the cache and raises `ReplayMiss` if absent; `off` raises. Also provide `ScriptedLLM` (returns queued responses) for tests. The cache key is the SHA-256 of model, prompt text and parameters.
