# mergeguard.models
# Defines the review-state contracts shared across deterministic checks and agent output.

from __future__ import annotations

from enum import Enum

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


from mergeguard.review_models import (
    Approval,
    ContextBlock,
    Decision,
    Rejection,
    ReviewContext,
    ReviewState,
    RiskBreakdown,
    SkepticVerdict,
)

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
