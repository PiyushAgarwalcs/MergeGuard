# Tests correctness and test-coverage agents using queued model responses.
# Calls are traced to a temporary database and never use network credentials.

from __future__ import annotations

import pytest

from mergeguard import storage
from mergeguard.agents.correctness_reviewer import run as run_correctness
from mergeguard.agents.test_reviewer import run as run_test_reviewer
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import PullRequest, ReviewContext, Severity, Source
from mergeguard.settings import settings


@pytest.fixture
def isolated_llm(tmp_path, monkeypatch):
    """Redirect trace writes and select scripted live mode."""
    monkeypatch.setattr(storage, "DATABASE_PATH", str(tmp_path / "traces.db"))
    monkeypatch.setattr(settings, "LLM_MODE", "live")


def _state() -> dict[str, object]:
    return {
        "pr": PullRequest(
            repo="example/project",
            number=3,
            head_sha="head",
            base_sha="base",
            title="Update behavior",
            body="",
            author="developer",
            diff="+return values[index + 1]",
            files=["src/service.py"],
        ),
        "context": ReviewContext(
            ci_status="failing",
            changed_test_files=["tests/test_service.py"],
            blocks=[],
        ),
        "run_id": "other-reviewers",
    }


def _finding(source: str, category: str) -> dict[str, object]:
    return {
        "id": "",
        "source": source,
        "category": category,
        "severity": "medium",
        "file": "src/service.py",
        "line_start": 1,
        "line_end": 1,
        "quote": "return values[index + 1]",
        "explanation": "The selected boundary is incorrect.",
        "suggestion": "Use the intended index.",
        "evidence": [],
    }


def test_correctness_reviewer_returns_scoped_finding(isolated_llm) -> None:
    """Return a Pydantic finding from the correctness category family."""
    result = run_correctness(
        _state(), client=ScriptedLLM([[_finding("correctness_reviewer", "off_by_one")]])
    )

    assert result["complete"] is True
    finding = result["findings"][0]
    assert finding.source == Source.CORRECTNESS
    assert finding.category == "off_by_one"
    assert finding.severity == Severity.MEDIUM


def test_correctness_reviewer_retries_out_of_scope_category(isolated_llm) -> None:
    """Fail visibly after retry when the model returns a security category."""
    client = ScriptedLLM(
        [
            [_finding("correctness_reviewer", "sql_injection")],
            [_finding("correctness_reviewer", "sql_injection")],
        ]
    )
    result = run_correctness(_state(), client=client)

    assert client.calls == 2
    assert result == {"findings": [], "complete": False}


def test_test_reviewer_returns_test_gap_finding(isolated_llm) -> None:
    """Return test-gap findings from the test reviewer category family."""
    result = run_test_reviewer(
        _state(), client=ScriptedLLM([[_finding("test_reviewer", "missing_test")]])
    )

    assert result["complete"] is True
    finding = result["findings"][0]
    assert finding.source == Source.TESTS
    assert finding.category == "missing_test"


def test_test_reviewer_accepts_empty_findings(isolated_llm) -> None:
    """Treat an explicit empty test review as complete."""
    result = run_test_reviewer(_state(), client=ScriptedLLM([[]]))

    assert result == {"findings": [], "complete": True}
