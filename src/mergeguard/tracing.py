# mergeguard.tracing
# Records LLM and system events so runs can be reconstructed from the SQLite store.

from __future__ import annotations

from typing import Any


def trace(event: str, **payload: Any) -> dict[str, Any]:
    return {"event": event, **payload}
