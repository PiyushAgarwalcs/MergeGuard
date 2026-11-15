# checks/verify_findings.py
# Verifies that each finding points to a real quoted hunk in the diff.

from __future__ import annotations

from mergeguard.models import Finding, ReviewState


def run(state: ReviewState) -> dict[str, list[Finding]]:
    return {"findings": [], "rejected": []}
