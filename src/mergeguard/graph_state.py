# mergeguard.graph_state
# Defines typed state channels shared by graph construction and node functions.

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from mergeguard.models import (
    Approval,
    Decision,
    Finding,
    PullRequest,
    Rejection,
    ReviewContext,
    SkepticVerdict,
)


class GraphState(TypedDict, total=False):
    """State channels used by the graph, including fan-out reducers."""

    pr: PullRequest
    repo_path: str
    run_id: str
    ci_status: str
    reviewable: bool
    context: ReviewContext
    findings: Annotated[list[Finding], operator.add]
    merged_findings: list[Finding]
    verified_findings: list[Finding]
    decision_findings: list[Finding]
    dismissed_findings: list[Finding]
    rejected: list[Rejection]
    verdicts: list[SkepticVerdict]
    incomplete: Annotated[bool, operator.or_]
    decision: Decision
    approval: Approval | None
    report: str
