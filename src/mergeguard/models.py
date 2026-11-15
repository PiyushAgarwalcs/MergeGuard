# mergeguard.models
# Defines the review-state contracts shared across deterministic checks and agent output.

from __future__ import annotations

from enum import Enum
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Source(str, Enum):
    RULE = "rule"
    SECURITY = "security_reviewer"
    CORRECTNESS = "correctness_reviewer"
    TESTS = "test_reviewer"


ALLOWED_CATEGORIES = {
    "hardcoded_secret",
    "sql_injection",
    "command_injection",
    "path_traversal",
    "unsafe_deserialization",
    "ssrf",
    "weak_crypto",
    "tls_verification_disabled",
    "xss",
    "missing_authorization",
    "insecure_randomness",
    "sensitive_data_in_logs",
    "off_by_one",
    "wrong_condition",
    "missing_null_check",
    "resource_leak",
    "swallowed_exception",
    "wrong_default",
    "missing_test",
    "test_weakened",
    "assertion_removed",
}


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: Source
    category: str
    severity: Severity
    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str
    explanation: str
    suggestion: str
    evidence: list[str] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if value not in ALLOWED_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(ALLOWED_CATEGORIES)}")
        return value

    @field_validator("line_end")
    @classmethod
    def validate_line_range(cls, value: int, info: object) -> int:
        data = info.data if hasattr(info, "data") else {}
        if "line_start" in data and value < data["line_start"]:
            raise ValueError("line_end must be greater than or equal to line_start")
        return value


class AddedLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    line_no: int
    text: str


class Hunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    new_start: int
    new_end: int
    text: str
    added: list[AddedLine] = Field(default_factory=list)


class PullRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: str
    number: int
    head_sha: str
    base_sha: str
    title: str
    body: str
    author: str
    diff: str
    files: list[str] = Field(default_factory=list)


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
    context: ReviewContext
    findings: list[Finding]
    rejected: list[Rejection]
    verdicts: list[SkepticVerdict]
    risk: RiskBreakdown
    decision: Decision
    approval: Approval | None
    report: str


__all__ = [
    "ALLOWED_CATEGORIES",
    "AddedLine",
    "Approval",
    "ContextBlock",
    "Decision",
    "Finding",
    "Hunk",
    "PullRequest",
    "Rejection",
    "ReviewContext",
    "ReviewState",
    "RiskBreakdown",
    "Severity",
    "SkepticVerdict",
    "Source",
]
