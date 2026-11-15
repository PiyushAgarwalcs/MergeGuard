# MergeGuard

MergeGuard is a LangGraph-based pull request review and merge gate. It reads diffs, applies deterministic checks, runs specialist reviewer agents, records every step to SQLite, and publishes a single PR decision.

Work in progress.

## Quick start

```bash
make install
make check
```
