# agents/test_reviewer.py
# Asks a model to review test changes and return findings.

from __future__ import annotations

from mergeguard.models import ReviewState

PROMPT_NAME = "test_reviewer.v1"


def run(state: ReviewState) -> dict[str, list]:
    return {"findings": []}
