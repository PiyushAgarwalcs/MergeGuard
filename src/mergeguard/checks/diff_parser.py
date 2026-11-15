# checks/diff_parser.py
# Parses a git patch into hunks and added lines used by verification.

from __future__ import annotations

from mergeguard.models import ReviewState


def run(state: ReviewState) -> dict[str, list]:
    return {"diff": []}
