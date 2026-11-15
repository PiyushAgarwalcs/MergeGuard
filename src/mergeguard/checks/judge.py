# checks/judge.py
# Computes the final risk score and outcome from verified findings and CI status.

from __future__ import annotations

from typing import cast

from mergeguard.models import Decision, Finding, PullRequest, ReviewState, Severity
from mergeguard.settings import (
    RISK_CI_FAILING,
    RISK_DEPENDENCY_FILE,
    RISK_HIGH_FINDING_WEIGHT,
    RISK_LOW_FINDING_WEIGHT,
    RISK_MEDIUM_FINDING_WEIGHT,
    RISK_SOURCE_WITHOUT_TEST,
    RISK_STRICTER_PATHS,
    settings,
)

SEVERITY_TO_WEIGHT = {
    Severity.HIGH: RISK_HIGH_FINDING_WEIGHT,
    Severity.MEDIUM: RISK_MEDIUM_FINDING_WEIGHT,
    Severity.LOW: RISK_LOW_FINDING_WEIGHT,
}


def _file_in_stricter_paths(files: list[str]) -> bool:
    stricter_prefixes = ("src/auth/", "infra/")
    return any(path.startswith(stricter_prefixes) for path in files)


def _count_changed_lines(findings: list[Finding]) -> int:
    total = 0
    for finding in findings:
        total += max(0, finding.line_end - finding.line_start + 1)
    return total


def _dependency_file_changed(files: list[str]) -> bool:
    names = {
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "poetry.lock",
        "package.json",
        "pipfile",
        "environment.yml",
    }
    return any(file.lower().split("/")[-1] in names for file in files)


def _source_without_test(files: list[str]) -> bool:
    lowered = {file.lower() for file in files}
    source_files = [path for path in lowered if path.startswith("src/") or path.endswith(".py")]
    test_files = [path for path in lowered if "test" in path.lower()]
    return bool(source_files) and not test_files


def calculate_risk(findings: list[Finding], files: list[str], ci_status: str | None) -> int:
    high_count = sum(1 for finding in findings if finding.severity == Severity.HIGH)
    medium_count = sum(1 for finding in findings if finding.severity == Severity.MEDIUM)
    low_count = sum(1 for finding in findings if finding.severity == Severity.LOW)
    score = 0
    score += min(high_count * RISK_HIGH_FINDING_WEIGHT, 60)
    score += min(medium_count * RISK_MEDIUM_FINDING_WEIGHT, 30)
    score += min(low_count * RISK_LOW_FINDING_WEIGHT, 10)

    if findings:
        changed_line_total = max(_count_changed_lines(findings), len(files) * 3)
    else:
        changed_line_total = len(files) * 2

    if changed_line_total > 400:
        score += 10
    if changed_line_total > 1000:
        score += 20
    if _file_in_stricter_paths(files):
        score += RISK_STRICTER_PATHS
    if _source_without_test(files):
        score += RISK_SOURCE_WITHOUT_TEST
    if ci_status in {"failing", "missing"}:
        score += RISK_CI_FAILING
    if _dependency_file_changed(files):
        score += RISK_DEPENDENCY_FILE

    return min(score, 100)


def judge_run(state: ReviewState | dict[str, object]) -> dict[str, Decision]:
    if isinstance(state, dict):
        findings = cast(list[Finding], state.get("findings", []))
        pr = cast(PullRequest | None, state.get("pr"))
        context = cast(object | None, state.get("context"))
    else:
        findings = cast(list[Finding], state.get("findings", []))
        pr = cast(PullRequest | None, state.get("pr"))
        context = cast(object | None, state.get("context"))

    files = getattr(pr, "files", []) if pr else []
    ci_status = getattr(context, "ci_status", None) if context else None
    risk_score = calculate_risk(findings, files, ci_status)
    reasons: list[str] = []

    if any(finding.severity == Severity.CRITICAL for finding in findings):
        return {
            "decision": Decision(
                outcome="block",
                reasons=["A verified critical finding blocks the change."],
                head_sha=getattr(pr, "head_sha", ""),
                risk_score=risk_score,
                complete=True,
            )
        }

    if not pr or not pr.diff:
        return {
            "decision": Decision(
                outcome="needs_human",
                reasons=["The review input was incomplete or missing."],
                head_sha=getattr(pr, "head_sha", ""),
                risk_score=risk_score,
                complete=False,
            )
        }

    if ci_status in {"failing", "missing"}:
        reasons.append("CI is failing or missing for this commit.")
        return {
            "decision": Decision(
                outcome="needs_human",
                reasons=reasons,
                head_sha=getattr(pr, "head_sha", ""),
                risk_score=risk_score,
                complete=True,
            )
        }

    if any(finding.severity == Severity.HIGH for finding in findings):
        reasons.append("A verified high-severity finding needs human review.")
        return {
            "decision": Decision(
                outcome="needs_human",
                reasons=reasons,
                head_sha=getattr(pr, "head_sha", ""),
                risk_score=risk_score,
                complete=True,
            )
        }

    if risk_score >= settings.RISK_THRESHOLD:
        reasons.append(
            f"Risk score {risk_score} meets or exceeds the threshold of {settings.RISK_THRESHOLD}."
        )
        return {
            "decision": Decision(
                outcome="needs_human",
                reasons=reasons,
                head_sha=getattr(pr, "head_sha", ""),
                risk_score=risk_score,
                complete=True,
            )
        }

    return {
        "decision": Decision(
            outcome="pass",
            reasons=[],
            head_sha=getattr(pr, "head_sha", ""),
            risk_score=risk_score,
            complete=True,
        )
    }


def run(state: ReviewState) -> dict[str, Decision]:
    return judge_run(state)
