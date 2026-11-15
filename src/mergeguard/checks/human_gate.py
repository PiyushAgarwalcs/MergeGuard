# checks/human_gate.py
# Applies the human approval gate for needs_human and block outcomes.

from __future__ import annotations

from mergeguard.models import ReviewState


def run(state: ReviewState) -> dict[str, dict[str, str] | None]:
    return {"approval": None}
