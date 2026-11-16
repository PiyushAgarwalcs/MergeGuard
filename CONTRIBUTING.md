# Contributing to MergeGuard

Thanks for your interest. This guide covers everything you need to get started, run the full check suite, and open a pull request.

## Dev setup

**Requirements:** Python 3.11, Git.

```bash
git clone <repo-url>
cd MergeGuard
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -e ".[dev]"
```

Copy `.env.example` to `.env`. Leave `LLM_MODE=replay` (the default) for offline work — no API key is required.

## Running the checks

```bash
make check
```

`make check` runs Ruff, Black, mypy, and the full pytest suite (294 tests). All must be green before you open a PR.

If `make` is unavailable on Windows, run the steps individually:

```powershell
python -m ruff check src tests evals dashboard
python -m black --check src tests evals dashboard
python -m mypy src
python -m pytest tests -x -q
```

## Offline / replay mode

Set `LLM_MODE=replay` (already the default) so reviewer calls use pre-recorded responses from `tests/fixtures/`. No network access or API key is needed. This is the **required mode for all CI runs and PR checks**.

```bash
LLM_MODE=replay python -m pytest tests -x -q
```

## Evaluation layers

The project has nine evaluation layers:

```bash
python -m evals.run --layer components --mode replay   # L1: 706 component cases
python -m evals.run --layer integration --mode replay  # L3: graph integration
python -m evals.run --layer pipeline --split test --mode replay  # L4/L5: end-to-end
python -m evals.run gate                               # regression gate
```

Always run with `--mode replay` in a PR context. Live-model runs (`--mode live`) require credentials and are excluded from CI.

## PR expectations

1. `make check` must pass with no errors or warnings.
2. All new features need tests. Add them in `tests/`.
3. Do not modify eval baselines (`evals/baselines/`) unless the change is intentional and justified in the PR description. Use `python -m evals.run baseline save` to update.
4. Do not add secrets, API keys, or real credentials anywhere in the codebase.
5. Keep source files in `src/mergeguard/`. Dashboard code lives in `dashboard/`, eval harness in `evals/`.

## File layout

| Path | Purpose |
|---|---|
| `src/mergeguard/` | Core library — agents, judge, scanner, CLI |
| `tests/` | Unit and component tests (run offline) |
| `evals/` | Evaluation harness, golden datasets, baselines |
| `dashboard/` | Streamlit dashboard |
| `docs/` | Architecture, evaluation, and threat-model docs |
| `examples/` | Sample diffs for local smoke tests |

## Questions

Open an issue or start a discussion. Keep issues focused: one bug or feature per issue.
