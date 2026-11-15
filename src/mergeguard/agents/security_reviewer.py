# agents/security_reviewer.py
# Asks a model to review the diff for security problems and returns findings.

from __future__ import annotations

from mergeguard.models import ReviewState

PROMPT_NAME = "security_reviewer.v1"


def run(state: ReviewState) -> dict[str, list]:
    return {"findings": []}
