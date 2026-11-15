# Agent instructions

This repository is built entirely by an AI coding agent following the plan in `plan/`.
Start with `plan/README.md`. It says what to read and how to work.

## Operating rules

1. Never ask the human questions. If something is unclear, use the default in `plan/DECISIONS.md`, or pick the simplest option that satisfies the plan, and record the choice in `plan/DECISIONS.md`.
2. Work in the order of `plan/PROGRESS.md`. Take the first unchecked task whose dependencies are done.
3. After every task run `make check`. Do not tick a task or move on while it fails.
4. Tick the task in `plan/PROGRESS.md` and commit with the message `P<phase>.<task>: <summary>`.
5. If a task needs a credential you do not have, follow `plan/08-configuration-and-credentials.md`: use fake or replay mode, log it in `plan/BLOCKERS.md`, and continue with other tasks.
6. Never put secrets in code, tests, logs, fixtures or commits.
7. Keep the code plain and readable: `plan/07-security-and-code-standards.md`.
8. End every session by updating the session notes in `plan/PROGRESS.md`, so a new session can resume exactly where this one stopped.
