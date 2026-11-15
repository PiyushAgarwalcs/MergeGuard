# Tests the security reviewer step with queued responses and no network access.
# The cases cover validated findings, failure after retry and a clean review.

from __future__ import annotations

import pytest

from mergeguard import storage
from mergeguard.agents.security_reviewer import run
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import PullRequest, ReviewContext, Severity, Source
from mergeguard.settings import settings
from mergeguard.storage import get_events


@pytest.fixture
def isolated_trace_db(tmp_path, monkeypatch):
    """Redirect trace writes to a disposable SQLite file."""
    database = tmp_path / "trace.db"
    monkeypatch.setattr(storage, "DATABASE_PATH", str(database))
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    return database


def _state() -> dict[str, object]:
    return {
        "pr": PullRequest(
            repo="example/project",
            number=1,
            head_sha="head",
            base_sha="base",
            title="Update query",
            body="",
            author="developer",
            diff="+query = 'SELECT * FROM users' + user_input",
            files=["app.py"],
        ),
        "context": ReviewContext(ci_status="missing", blocks=[]),
        "run_id": "security-agent-test",
    }


def _finding() -> dict[str, object]:
    return {
        "id": "",
        "source": "security_reviewer",
        "category": "sql_injection",
        "severity": "high",
        "file": "app.py",
        "line_start": 3,
        "line_end": 3,
        "quote": "query = 'SELECT * FROM users' + user_input",
        "explanation": "Input changes the SQL query structure.",
        "suggestion": "Use a parameterized query.",
        "evidence": ["C-1"],
    }


def test_security_reviewer_returns_validated_findings(isolated_trace_db) -> None:
    """Return typed findings and a complete status after valid model output."""
    result = run(_state(), client=ScriptedLLM([[_finding()]]))

    assert result["complete"] is True
    finding = result["findings"][0]
    assert finding.category == "sql_injection"
    assert finding.severity == Severity.HIGH
    assert finding.source == Source.SECURITY
    event = next(
        event for event in get_events("security-agent-test") if event["kind"] == "llm_call"
    )
    assert event["prompt_version"] == "security_reviewer.v1"


def test_security_reviewer_marks_invalid_output_failed_after_retry(isolated_trace_db) -> None:
    """Retry one malformed reply and return incomplete after the second failure."""
    client = ScriptedLLM(["not json", "still not json"])
    result = run(_state(), client=client)

    assert client.calls == 2
    assert result == {"findings": [], "complete": False}
    failures = [
        event for event in get_events("security-agent-test") if event["kind"] == "agent_failed"
    ]
    assert len(failures) == 1
    assert failures[0]["payload"] == {"error_type": "InvalidModelOutput"}


def test_security_reviewer_accepts_empty_findings(isolated_trace_db) -> None:
    """Treat a valid empty result as a complete review with no findings."""
    result = run(_state(), client=ScriptedLLM([[]]))

    assert result == {"findings": [], "complete": True}
