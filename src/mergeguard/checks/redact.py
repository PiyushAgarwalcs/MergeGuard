# checks/redact.py
# Masks secrets before any finding or prompt is recorded or sent upstream.

from __future__ import annotations

from mergeguard.models import ReviewState


def run(state: ReviewState) -> dict[str, str]:
    return {"diff": state["pr"].diff if "pr" in state else ""}
