# mergeguard.review_models
# Defines context, decision, approval, and graph-state contracts.

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from mergeguard.models import Finding, Hunk, PullRequest


class ContextBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["caller", "test", "sibling", "ci", "config"]
    path: str
    text: str


class ReviewContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocks: list[ContextBlock] = Field(default_factory=list)
    ci_status: Literal["passing", "failing", "missing"] = "passing"
    changed_source_files: list[str] = Field(default_factory=list)
    changed_test_files: list[str] = Field(default_factory=list)


class Rejection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding: Finding
    reason: Literal[
        "QUOTE_NOT_IN_DIFF",
        "LINES_OUT_OF_RANGE",
        "UNKNOWN_EVIDENCE",
        "UNKNOWN_CATEGORY",
        "FILE_NOT_IN_DIFF",
    ]


class SkepticVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    verdict: Literal["upheld", "refuted", "unclear"]
    reason: str


class RiskBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = 0
    parts: dict[str, int] = Field(default_factory=dict)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["pass", "needs_human", "block"]
    reasons: list[str] = Field(default_factory=list)
    head_sha: str
    risk_score: int
    complete: bool = True


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["approve", "override", "dismiss"]
    by_user: str
    reason: str
    head_sha: str
    finding_id: str | None = None


class ReviewState(TypedDict, total=False):
    pr: PullRequest
    repo_path: str
    ci_status: Literal["passing", "failing", "missing"]
    run_id: str
    context: ReviewContext
    finding: Finding
    hunk: Hunk
    complete: bool
    findings: list[Finding]
    verified_findings: list[Finding]
    decision_findings: list[Finding]
    rejected: list[Rejection]
    verdicts: list[SkepticVerdict]
    risk: RiskBreakdown
    decision: Decision
    approval: Approval | None
    report: str
