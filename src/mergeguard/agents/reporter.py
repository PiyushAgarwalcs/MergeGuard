# agents/reporter.py
# Produces the review comment after the decision is determined.

from __future__ import annotations

from mergeguard.models import ReviewState

PROMPT_NAME = "reporter.v1"


def run(state: ReviewState) -> dict[str, str]:
    return {"report": ""}
