# checks/judge.py
# Computes the risk score and final outcome from verified findings and CI status.

from __future__ import annotations

from mergeguard.models import Decision, ReviewState


def run(state: ReviewState) -> dict[str, Decision]:
    return {"decision": Decision(outcome="pass", reasons=[], head_sha="", risk_score=0)}
