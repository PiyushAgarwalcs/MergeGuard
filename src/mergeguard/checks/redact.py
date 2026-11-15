# checks/redact.py
# Masks secrets before any finding or prompt is recorded or sent upstream.

from __future__ import annotations

import re

from mergeguard.models import ReviewState

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "aws_key",
        re.compile(
            r"(?i)(?:AWS|aws)[_-]?(?:SECRET|secret)[_-]?ACCESS[_-]?KEY\s*[:=]\s*[\"']?"
            r"[A-Za-z0-9/+=]{16,}[\"']?"
        ),
    ),
    (
        "api_key",
        re.compile(
            r"(?i)(?:api[_-]?key|token|secret)\s*[:=]\s*[\"']?[A-Za-z0-9_\-+/=.]{12,}[\"']?"
        ),
    ),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----.*?"
            r"-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    (
        "jwt",
        re.compile(r"(?i)eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*"),
    ),
    (
        "secret_assignment",
        re.compile(
            r"(?i)(?:password|passwd|secret|token)\s*[:=]\s*[\"']?[A-Za-z0-9_\-+/=.:]{12,}[\"']?"
        ),
    ),
]


def redact_diff(diff_text: str) -> str:
    redacted = diff_text
    for label, pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(f"[REDACTED:{label}]", redacted)
    return redacted


def run(state: ReviewState) -> dict[str, str]:
    diff_text = state["pr"].diff if "pr" in state else ""
    return {"diff": redact_diff(diff_text)}
