# checks/collect_context.py
# Collects the PR body, changed files and context blocks needed by the review pipeline.

from __future__ import annotations

from mergeguard.models import ReviewContext, ReviewState


def run(state: ReviewState) -> dict[str, ReviewContext]:
    return {"context": ReviewContext()}
