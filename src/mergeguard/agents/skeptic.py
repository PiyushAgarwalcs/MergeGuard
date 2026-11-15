# agents/skeptic.py
# Reviews a finding and decides whether it is upheld, refuted or unclear.

from __future__ import annotations

from mergeguard.models import ReviewState

PROMPT_NAME = "skeptic.v1"


def run(state: ReviewState) -> dict[str, list]:
    return {"verdicts": []}
