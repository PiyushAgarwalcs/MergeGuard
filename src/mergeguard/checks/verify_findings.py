# checks/verify_findings.py
# Verifies that each finding points to a real quoted hunk and valid context block in the diff.

from __future__ import annotations

from mergeguard.checks.diff_parser import parse_diff
from mergeguard.models import ALLOWED_CATEGORIES, Finding, Rejection, ReviewContext, ReviewState


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def verify_findings(
    findings: list[Finding],
    diff_text: str,
    context: ReviewContext | None = None,
) -> tuple[list[Finding], list[Rejection]]:
    hunks = parse_diff(diff_text)
    hunk_map: dict[str, list] = {}
    for hunk in hunks:
        hunk_map.setdefault(hunk.file, []).append(hunk)

    valid: list[Finding] = []
    rejected: list[Rejection] = []
    known_evidence_ids = {block.id for block in (context.blocks if context else [])}

    for finding in findings:
        if finding.category not in ALLOWED_CATEGORIES:
            rejected.append(Rejection(finding=finding, reason="UNKNOWN_CATEGORY"))
            continue
        if finding.file not in hunk_map:
            rejected.append(Rejection(finding=finding, reason="FILE_NOT_IN_DIFF"))
            continue
        hunk_match = None
        for hunk in hunk_map[finding.file]:
            if hunk.new_start <= finding.line_start <= finding.line_end <= hunk.new_end:
                hunk_match = hunk
                break
        if hunk_match is None:
            rejected.append(Rejection(finding=finding, reason="LINES_OUT_OF_RANGE"))
            continue
        quote = _collapse_whitespace(finding.quote)
        if not quote:
            rejected.append(Rejection(finding=finding, reason="QUOTE_NOT_IN_DIFF"))
            continue
        added_text = "\n".join(item.text for item in hunk_match.added)
        hunk_text = _collapse_whitespace(added_text)
        if quote not in hunk_text:
            rejected.append(Rejection(finding=finding, reason="QUOTE_NOT_IN_DIFF"))
            continue
        if finding.evidence:
            unknown = [item for item in finding.evidence if item not in known_evidence_ids]
            if unknown:
                rejected.append(Rejection(finding=finding, reason="UNKNOWN_EVIDENCE"))
                continue
        valid.append(finding)

    return valid, rejected


def run(state: ReviewState) -> dict[str, list[Finding] | list[Rejection]]:
    diff_text = state["pr"].diff if "pr" in state else ""
    context = state.get("context")
    findings = state.get("findings", [])
    valid, rejected = verify_findings(findings, diff_text, context)
    return {"findings": valid, "rejected": rejected}
