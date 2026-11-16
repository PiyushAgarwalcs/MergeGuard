# Phase 2: Storage and tracing

Goal: every run can be reconstructed from SQLite.
Depends on: Phase 1. Read: `03-observability.md`.

## Tasks

- [x] **P2.1** `storage.py`: open SQLite with WAL and busy timeout 5000 ms, create all tables from `03-observability.md` with a simple migration function, and provide small functions to insert and query each table. No SQL outside this file except in `dashboard/queries.py` (read-only).
- [x] **P2.2** `tracing.py`: `span`, `record_llm_call`, `record`, cost computation from `config/prices.yml` (create it with a comment and no prices), structured log lines. Privacy mode stores hashes instead of diff text.
- [x] **P2.3** Wire `mergeguard review` to create a `runs` row, wrap each step in a span, store findings and the decision. Add `mergeguard runs list` and `mergeguard runs show <run_id>` that print the trace from the database.
- [x] **P2.4** Tests: a run can be fully reconstructed from the database; privacy mode stores no diff text; secrets never appear in stored events or logs; two concurrent writers do not corrupt the file.

## Verify

`make check`; run `mergeguard review` on an example and `mergeguard runs show <id>` prints every step.

## Done when

All tasks ticked.
