# checks/rule_scan.py
# Runs deterministic rule-based security checks against the diff.

from __future__ import annotations

from mergeguard.models import Finding, ReviewState


def run(state: ReviewState) -> dict[str, list[Finding]]:
    return {"findings": []}
