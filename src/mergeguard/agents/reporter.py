# Writes the deterministic markdown review comment from verified findings.
# A mechanical check ties every cited finding id, file, line, and count to input.

from __future__ import annotations

import re
from collections import Counter

from mergeguard.models import Decision, Finding, ReviewState

PROMPT_NAME = "reporter.v1"
COUNT_PATTERN = re.compile(r"^\*\*Verified findings:\*\* (\d+)$", re.MULTILINE)
CITATION_PATTERN = re.compile(
    r"^- \*\*(?P<id>[^|]+) \| (?P<severity>[^|]+) \| (?P<category>[^*]+)\*\* — `(?P<file>[^`]+):L(?P<start>\d+)(?:-L(?P<end>\d+))?`$",
    re.MULTILINE,
)


def run(state: ReviewState) -> dict[str, str]:
    """Create a faithful markdown comment from the verified review state."""
    findings = state.get("decision_findings", state.get("findings", []))
    decision = state.get("decision")
    if decision is None:
        report = "## MergeGuard review\n\nReview is incomplete; a decision was not produced.\n"
        return {"report": report}
    comment = render_comment(findings, decision)
    if not is_faithful_comment(comment, findings):
        return {"report": "## MergeGuard review\n\nReport citations failed verification.\n"}
    return {"report": comment}


def render_comment(findings: list[Finding], decision: Decision) -> str:
    """Render decision, verified findings, and dismissal instructions as Markdown."""
    ordered = sorted(findings, key=lambda item: (item.file, item.line_start, item.id))
    lines = [
        "## MergeGuard review",
        "",
        f"**Decision:** {decision.outcome}",
        f"**Verified findings:** {len(ordered)}",
        "",
        "### Findings",
    ]
    if not ordered:
        lines.extend(["", "No verified findings."])
    for finding in ordered:
        end = f"-L{finding.line_end}" if finding.line_end != finding.line_start else ""
        lines.extend(
            [
                "",
                (
                    f"- **{finding.id} | {finding.severity.value.upper()} | {finding.category}** — `"
                    f"{finding.file}:L{finding.line_start}{end}`"
                ),
                f"  - Evidence: {_inline_code(finding.quote)}",
                f"  - Explanation: {_safe_text(finding.explanation)}",
                f"  - Suggested fix: {_safe_text(finding.suggestion)}",
                f"  - To dismiss: comment `/mergeguard dismiss {finding.id} <reason>`.",
            ]
        )
    lines.extend(["", "### Decision reasons", ""])
    lines.extend(f"- {_safe_text(reason)}" for reason in decision.reasons)
    if not decision.reasons:
        lines.append("- No additional reasons.")
    return "\n".join(lines).rstrip() + "\n"


def is_faithful_comment(comment: str, findings: list[Finding]) -> bool:
    """Check that each finding citation and the reported count map to inputs."""
    count_matches = COUNT_PATTERN.findall(comment)
    if count_matches != [str(len(findings))]:
        return False
    expected = Counter(
        (
            item.id,
            item.severity.value.upper(),
            item.category,
            item.file,
            item.line_start,
            item.line_end,
        )
        for item in findings
    )
    actual = Counter(
        (
            match.group("id"),
            match.group("severity"),
            match.group("category"),
            match.group("file"),
            int(match.group("start")),
            int(match.group("end") or match.group("start")),
        )
        for match in CITATION_PATTERN.finditer(comment)
    )
    return actual == expected


def _inline_code(value: str) -> str:
    """Quote untrusted text as a one-line Markdown code span."""
    normalized = " ".join(value.split()).replace("`", "'")
    return f"`{normalized}`"


def _safe_text(value: str) -> str:
    """Keep model-authored prose on one Markdown line without fake citations."""
    normalized = " ".join(value.split())
    normalized = re.sub(r"\b\d+\s+(?:verified\s+)?findings?\b", "findings", normalized)
    normalized = re.sub(r"(?:[\w./-]+\.[A-Za-z0-9]+):L\d+(?:-L?\d+)?", "file reference", normalized)
    return normalized.replace("\r", " ").replace("\n", " ")
