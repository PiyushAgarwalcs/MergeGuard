# checks/rule_scan.py
# Runs deterministic rule-based security checks against the new lines in the diff.

from __future__ import annotations

import re

from mergeguard.checks.diff_parser import parse_diff
from mergeguard.models import Finding, Hunk, ReviewState, Severity, Source

SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
}

RULES: list[tuple[str, str, str, str, str]] = [
    (
        "hardcoded_secret",
        r"(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*[\"'](?!(?:.*os\.environ|.*fixture|.*dummy|.*sample|.*example))[A-Za-z0-9_\-+/=.:]{8,}[\"']",
        "high",
        "hardcoded_secret",
        "Hardcoded secret material is committed in code.",
    ),
    (
        "verify_false",
        r"verify\s*=\s*False",
        "high",
        "tls_verification_disabled",
        "Requests with certificate verification disabled are unsafe.",
    ),
    (
        "shell_true",
        r"shell\s*=\s*True|subprocess\.(?:run|Popen|call)\([^\n]*shell\s*=\s*True",
        "high",
        "command_injection",
        "A shell command is spawned with untrusted input.",
    ),
    (
        "pickle_loads",
        r"pickle\.loads\s*\(",
        "high",
        "unsafe_deserialization",
        "Unpickling untrusted data is dangerous.",
    ),
    (
        "yaml_load",
        r"yaml\.load\s*\(",
        "high",
        "unsafe_deserialization",
        "YAML is loaded without a safe loader.",
    ),
    (
        "eval_exec",
        r"\b(?:eval|exec)\s*\(",
        "high",
        "command_injection",
        "Dynamic execution can run attacker-controlled code.",
    ),
    (
        "sql_execute",
        r"\b(?:execute|executemany|executescript)\s*\([^\n]*(?:f[\"']|%|\+)",
        "high",
        "sql_injection",
        "SQL is assembled dynamically before execution.",
    ),
    (
        "weak_hash",
        r"\b(?:md5|sha1)\s*\(",
        "medium",
        "weak_crypto",
        "Weak hashing is used for sensitive data.",
    ),
    (
        "random_token",
        r"\brandom\.(?:randint|getrandbits|random|seed)\s*\(",
        "medium",
        "insecure_randomness",
        "Randomness is being used for security-sensitive tokens.",
    ),
    (
        "debug_flag",
        r"\b(debug|DEBUG)\s*[:=]\s*True\b",
        "low",
        "wrong_default",
        "Debug mode is enabled in a production path.",
    ),
    (
        "logging_secret",
        r"\b(?:log|logger|logging)\.[A-Za-z_]+\([^\n]*(?:password|token|secret)",
        "medium",
        "sensitive_data_in_logs",
        "Sensitive values are being logged.",
    ),
]


def _skip_false_positive(line: str) -> bool:
    lower = line.lower()
    if "os.environ.get" in lower or "os.environ[" in lower:
        return True
    if re.search(r"\b(?:test|fixture|dummy|sample|example)[A-Za-z0-9_]*\s*[:=]", line, re.I):
        return True
    if "fixture" in lower or "dummy" in lower or "sample" in lower or "example" in lower:
        return True
    if re.search(r"\b[A-Z_]{3,}_KEY\s*=\s*os\.environ", line):
        return True
    return False


def _findings_for_hunk(hunk: Hunk, diff_file: str) -> list[Finding]:
    findings: list[Finding] = []
    for added in hunk.added:
        text = added.text.strip()
        if not text:
            continue
        if _skip_false_positive(text):
            continue
        for _, pattern, level, category, explanation in RULES:
            if re.search(pattern, text, re.IGNORECASE):
                findings.append(
                    Finding(
                        id="",
                        source=Source.RULE,
                        category=category,
                        severity=SEVERITY_MAP[level],
                        file=diff_file or hunk.file,
                        line_start=added.line_no,
                        line_end=added.line_no,
                        quote=text,
                        explanation=explanation,
                        suggestion="Review the call and replace it with a safer API or a validated input path.",
                        evidence=[],
                    )
                )
    return findings


def scan_diff(diff_text: str) -> list[Finding]:
    findings: list[Finding] = []
    for hunk in parse_diff(diff_text):
        findings.extend(_findings_for_hunk(hunk, hunk.file))
    return findings


def run(state: ReviewState) -> dict[str, list[Finding]]:
    diff_text = state["pr"].diff if "pr" in state else ""
    return {"findings": scan_diff(diff_text)}
