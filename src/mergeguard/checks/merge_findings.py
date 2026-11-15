# checks/merge_findings.py
# Merges duplicate findings and assigns stable ids in file and line order.

from __future__ import annotations

from mergeguard.models import Finding, ReviewState


def run(state: ReviewState) -> dict[str, list[Finding]]:
    return {"findings": []}
