# Tests deterministic reviewer comments and mechanical citation faithfulness.
# Fabricated file, line, or finding-count references must fail verification.

from __future__ import annotations

from mergeguard.agents.reporter import is_faithful_comment, render_comment, run
from mergeguard.models import Decision, Finding, Severity, Source


def _finding() -> Finding:
    return Finding(
        id="F-1",
        source=Source.SECURITY,
        category="sql_injection",
        severity=Severity.HIGH,
        file="app/db.py",
        line_start=12,
        line_end=13,
        quote="query = build_query(value)",
        explanation="Two findings are at other.py:L99.",
        suggestion="Use a parameterized query.",
        evidence=[],
    )


def _decision() -> Decision:
    return Decision(
        outcome="needs_human",
        reasons=["A verified high-severity finding requires review."],
        head_sha="abc123",
        risk_score=30,
    )


def test_reporter_renders_verified_finding_and_decision() -> None:
    """Render all required finding fields, decision reasons, and dismissal command."""
    finding = _finding()
    comment = render_comment([finding], _decision())

    assert "**Decision:** needs_human" in comment
    assert "**Verified findings:** 1" in comment
    assert "F-1 | HIGH | sql_injection" in comment
    assert "`app/db.py:L12-L13`" in comment
    assert "query = build_query(value)" in comment
    assert "Use a parameterized query." in comment
    assert "/mergeguard dismiss F-1 <reason>" in comment
    assert "other.py:L99" not in comment
    assert is_faithful_comment(comment, [finding])


def test_reporter_rejects_fabricated_citation_or_count() -> None:
    """Reject comments whose file, line, or finding count differs from verified data."""
    finding = _finding()
    comment = render_comment([finding], _decision())

    assert not is_faithful_comment(comment.replace("app/db.py:L12-L13", "other.py:L99"), [finding])
    assert not is_faithful_comment(
        comment.replace("Verified findings:** 1", "Verified findings:** 2"), [finding]
    )
    assert not is_faithful_comment(comment.replace("L12-L13", "L12-L14"), [finding])


def test_reporter_handles_empty_verified_findings() -> None:
    """Report zero findings without adding any unsupported citations."""
    result = run({"findings": [], "decision": _decision()})

    assert "**Verified findings:** 0" in result["report"]
    assert "No verified findings." in result["report"]
    assert is_faithful_comment(result["report"], [])
