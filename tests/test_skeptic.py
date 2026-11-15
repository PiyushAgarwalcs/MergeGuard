# Tests skeptic input selection and findings with scripted responses.
# Ineligible findings must not consume a model response.

from __future__ import annotations

import pytest

from mergeguard import storage
from mergeguard.agents.skeptic import review_verified_findings
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import ContextBlock, Finding, ReviewContext, Severity, Source
from mergeguard.settings import settings

DIFF = """diff --git a/src/service.py b/src/service.py
--- a/src/service.py
+++ b/src/service.py
@@ -1,1 +1,2 @@
 existing()
+dangerous_call(user_value)
"""


@pytest.fixture
def isolated_llm(tmp_path, monkeypatch):
    """Redirect trace writes and select scripted live mode."""
    monkeypatch.setattr(storage, "DATABASE_PATH", str(tmp_path / "traces.db"))
    monkeypatch.setattr(settings, "LLM_MODE", "live")


def _finding(source: Source, severity: Severity, finding_id: str) -> Finding:
    return Finding(
        id=finding_id,
        source=source,
        category="command_injection",
        severity=severity,
        file="src/service.py",
        line_start=2,
        line_end=2,
        quote="dangerous_call(user_value)",
        explanation="Untrusted input reaches a shell.",
        suggestion="Pass a fixed argument vector.",
        evidence=["C-1"],
    )


def test_skeptic_filters_rule_and_low_findings(isolated_llm) -> None:
    """Only a medium-or-higher verified LLM finding reaches the skeptic."""
    findings = [
        _finding(Source.RULE, Severity.HIGH, "F-rule"),
        _finding(Source.SECURITY, Severity.LOW, "F-low"),
        _finding(Source.SECURITY, Severity.MEDIUM, "F-eligible"),
    ]
    context = ReviewContext(
        ci_status="passing",
        blocks=[ContextBlock(id="C-1", kind="caller", path="src/caller.py", text="calls function")],
    )
    client = ScriptedLLM(
        [
            {
                "finding_id": "F-eligible",
                "verdict": "upheld",
                "reason": "The changed call receives untrusted input.",
            }
        ]
    )

    result = review_verified_findings(
        findings, DIFF, context, run_id="skeptic-filter", client=client
    )

    assert client.calls == 1
    assert result["complete"] is True
    assert [item.finding_id for item in result["verdicts"]] == ["F-eligible"]


def test_skeptic_marks_wrong_finding_id_incomplete(isolated_llm) -> None:
    """Reject a verdict that refers to a different finding id."""
    finding = _finding(Source.CORRECTNESS, Severity.HIGH, "F-1")
    client = ScriptedLLM(
        [{"finding_id": "F-2", "verdict": "refuted", "reason": "Not the reviewed finding."}]
    )

    result = review_verified_findings(
        [finding], DIFF, ReviewContext(ci_status="missing"), client=client
    )

    assert client.calls == 1
    assert result == {"verdicts": [], "complete": False}


def test_skeptic_skips_finding_without_matching_hunk(isolated_llm) -> None:
    """Mark review incomplete rather than asking with an unrelated hunk."""
    finding = _finding(Source.TESTS, Severity.CRITICAL, "F-test")
    client = ScriptedLLM([])

    result = review_verified_findings(
        [finding], "", ReviewContext(ci_status="missing"), client=client
    )

    assert result == {"verdicts": [], "complete": False}
    assert client.calls == 0
