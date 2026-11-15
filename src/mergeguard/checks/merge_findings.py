# checks/merge_findings.py
# Merges duplicates and assigns stable ids by file and line order.

from __future__ import annotations

from mergeguard.models import Finding, ReviewState, Severity, Source


def _severity_rank(severity: Severity) -> int:
    return {Severity.CRITICAL: 5, Severity.HIGH: 4, Severity.MEDIUM: 3, Severity.LOW: 2}[severity]


def _source_rank(source: Source) -> int:
    return 1 if source == Source.RULE else 0


def _ranges_overlap(left: Finding, right: Finding) -> bool:
    return (
        left.file == right.file
        and left.category == right.category
        and not (left.line_end < right.line_start or right.line_end < left.line_start)
    )


def merge_findings(findings: list[Finding]) -> list[Finding]:
    kept: list[Finding] = []
    for candidate in findings:
        merged = False
        for existing in kept:
            if not _ranges_overlap(existing, candidate):
                continue
            if _severity_rank(candidate.severity) > _severity_rank(existing.severity):
                existing.severity = candidate.severity
                existing.quote = candidate.quote
                existing.explanation = candidate.explanation
                existing.suggestion = candidate.suggestion
                existing.evidence = candidate.evidence
            elif _severity_rank(candidate.severity) == _severity_rank(existing.severity):
                if _source_rank(candidate.source) > _source_rank(existing.source):
                    existing.source = candidate.source
                    existing.quote = candidate.quote
                    existing.explanation = candidate.explanation
                    existing.suggestion = candidate.suggestion
                    existing.evidence = candidate.evidence
            merged = True
            break
        if not merged:
            kept.append(candidate)

    ordered = sorted(
        kept, key=lambda item: (item.file, item.line_start, item.line_end, item.category)
    )
    for index, item in enumerate(ordered, start=1):
        item.id = f"F-{index}"
    return ordered


def run(state: ReviewState) -> dict[str, list[Finding]]:
    findings = state.get("findings", [])
    return {"findings": merge_findings(findings)}
