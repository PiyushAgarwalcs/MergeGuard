# Phase 0: Skeleton

Goal: an installable package, one command that checks everything, CI, and typed contracts.
Depends on: nothing. Read: `02-architecture.md`, `07-security-and-code-standards.md`.

## Tasks

- [x] **P0.1** Create `pyproject.toml` (setuptools, src layout, package `mergeguard`, console script `mergeguard = mergeguard.cli:app`, dependencies and extras `eval` and `dev` exactly as in DECISIONS #4 to #6). Create `src/mergeguard/` with every module and package listed in `02-architecture.md`, each starting with its two-line header comment and otherwise empty. Create `tests/test_smoke.py` that imports `mergeguard`.
- [x] **P0.2** Create `Makefile` with targets: `install` (`pip install -e '.[dev]'`), `check` (ruff, black --check, mypy src, pytest -q), `test`, `fmt`, `eval-fast`, `serve`, `dashboard`. `make check` must work from a fresh clone after `make install`.
- [x] **P0.3** Write `settings.py` (typed settings from environment and `.env`; thresholds and risk weights from `02-architecture.md` as named constants; never fails when credentials are missing) and `models.py` (every contract in `02-architecture.md`). Tests: models validate and reject bad input; settings load with an empty environment.
- [x] **P0.4** Create `.github/workflows/ci.yml` (Python 3.11, install, `make check`), a `README.md` skeleton (title, one-paragraph pitch, "work in progress", quick start placeholder), `docs/how-it-works.md`, `docs/evaluation.md`, `docs/threat-model.md` stubs, and `.mergeguard.yml.example` from `01-decisions-and-scope.md`.

## Verify

`make install && make check`

## Done when

`make check` passes on a clean checkout and CI workflow exists.
