# Tests approval parsing, repository authorization, persistence and checkpoint resume.

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from mergeguard import storage
from mergeguard.checks import human_gate
from mergeguard.graph import build_graph
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import (
    Approval,
    Decision,
    Finding,
    PullRequest,
    ReviewContext,
    Severity,
    Source,
)
from mergeguard.settings import settings

DIFF = """diff --git a/src/service.py b/src/service.py
--- a/src/service.py
+++ b/src/service.py
@@ -1 +1 @@
+return value
"""


def _state(root: Path, outcome: str = "needs_human") -> dict:
    (root / ".mergeguard.yml").write_text(
        yaml.safe_dump({"approvers": ["reviewer"]}), encoding="utf-8"
    )
    finding = Finding(
        id="F-1",
        source=Source.RULE,
        category="command_injection",
        severity=Severity.HIGH,
        file="src/service.py",
        line_start=1,
        line_end=1,
        quote="return value",
        explanation="unsafe",
        suggestion="fix it",
    )
    return {
        "pr": PullRequest(
            repo="acme/app",
            number=5,
            head_sha="head-5",
            base_sha="base",
            title="change",
            body="",
            author="dev",
            diff=DIFF,
            files=["src/service.py"],
        ),
        "repo_path": str(root),
        "run_id": "gate-run",
        "context": ReviewContext(ci_status="missing"),
        "decision": Decision(
            outcome=outcome, reasons=["review needed"], head_sha="head-5", risk_score=30
        ),
        "decision_findings": [finding],
        "complete": True,
    }


def test_command_parser_requires_exact_commands_and_reasons() -> None:
    assert human_gate.parse_command("/mergeguard approve").kind == "approve"
    override = human_gate.parse_command("/mergeguard override reviewed operational risk")
    assert override.reason == "reviewed operational risk"
    dismiss = human_gate.parse_command("/mergeguard dismiss f-1 false alarm")
    assert dismiss.finding_id == "F-1"
    with pytest.raises(human_gate.ApprovalRejected, match="requires a reason"):
        human_gate.parse_command("/mergeguard override")
    with pytest.raises(human_gate.ApprovalRejected):
        human_gate.parse_command("/mergeguard approve extra")


def test_commands_require_approver_and_current_head(tmp_path: Path) -> None:
    state = _state(tmp_path)
    command = human_gate.parse_command("/mergeguard approve")
    with pytest.raises(human_gate.ApprovalRejected, match="not listed"):
        human_gate.authorize_command(
            command,
            "stranger",
            {"reviewer"},
            head_sha="head-5",
            decision=state["decision"],
            findings=state["decision_findings"],
        )
    stale = Approval(kind="approve", by_user="reviewer", reason="", head_sha="old-head")
    with pytest.raises(human_gate.ApprovalRejected, match="stale"):
        human_gate._validate_approval(stale, state)
    with pytest.raises(human_gate.ApprovalRejected, match="active"):
        human_gate.authorize_command(
            human_gate.parse_command("/mergeguard dismiss F-8 false alarm"),
            "reviewer",
            {"reviewer"},
            head_sha="head-5",
            decision=state["decision"],
            findings=state["decision_findings"],
        )


def test_override_and_dismiss_rules() -> None:
    state = {
        "decision": Decision(outcome="block", head_sha="h", risk_score=100),
        "pr": PullRequest(
            repo="a/b",
            number=1,
            head_sha="h",
            base_sha="b",
            title="",
            body="",
            author="x",
            diff=DIFF,
            files=["src/service.py"],
        ),
        "repo_path": ".",
        "decision_findings": [],
    }
    approval = human_gate.authorize_command(
        human_gate.parse_command("/mergeguard override approved exception"),
        "reviewer",
        {"reviewer"},
        head_sha="h",
        decision=state["decision"],
        findings=[],
    )
    result = human_gate._apply_approval(approval, state)
    assert result["decision"].outcome == "pass"
    with pytest.raises(human_gate.ApprovalRejected, match="only to a block"):
        human_gate.authorize_command(
            human_gate.parse_command("/mergeguard override reason"),
            "reviewer",
            {"reviewer"},
            head_sha="h",
            decision=Decision(outcome="needs_human", head_sha="h", risk_score=0),
            findings=[],
        )


def test_accepted_command_is_persisted_and_resumes_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "approval.db"
    monkeypatch.setattr(storage, "DATABASE_PATH", str(database))
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    state = _state(tmp_path)
    clients = {
        "security_reviewer": ScriptedLLM([[]]),
        "correctness_reviewer": ScriptedLLM([[]]),
        "test_reviewer": ScriptedLLM([[]]),
        "skeptic": ScriptedLLM([]),
    }
    thread_id = "acme/app#5@head-5"

    async def resume():
        async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
            await saver.setup()
            graph = build_graph(checkpointer=saver, clients=clients)
            initial = await graph.ainvoke(
                {
                    "pr": state["pr"],
                    "repo_path": state["repo_path"],
                    "run_id": "gate-run",
                    "ci_status": "missing",
                    "incomplete": False,
                },
                config={"configurable": {"thread_id": thread_id}},
            )
            assert initial["decision"].outcome == "needs_human"
            assert "__interrupt__" in initial
            return await human_gate.resume_review(
                graph, thread_id, "/mergeguard approve", "Reviewer"
            )

    result = asyncio.run(resume())
    assert result["approval"].head_sha == "head-5"
    assert result["decision"].outcome == "pass"
    assert result["report"].startswith("## MergeGuard review")
    connection = storage.connect(database)
    try:
        feedback = connection.execute("SELECT action, by_user FROM feedback").fetchone()
        assert tuple(feedback) == ("approve", "Reviewer")
        events = connection.execute("SELECT kind, payload FROM events").fetchall()
        assert any(row["kind"] == "approval_action" for row in events)
        payload = next(
            json.loads(row["payload"]) for row in events if row["kind"] == "approval_action"
        )
        assert payload["head_sha"] == "head-5"
    finally:
        connection.close()


def test_dismissal_can_reinterrupt_then_accept_a_second_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "dismiss-resume.db"
    monkeypatch.setattr(storage, "DATABASE_PATH", str(database))
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    (tmp_path / ".mergeguard.yml").write_text(
        yaml.safe_dump({"approvers": ["reviewer"]}), encoding="utf-8"
    )
    risky_diff = """diff --git a/src/service.py b/src/service.py
--- a/src/service.py
+++ b/src/service.py
@@ -1 +1 @@
+subprocess.run(user, shell=True)
"""
    pr = PullRequest(
        repo="acme/app",
        number=6,
        head_sha="head-6",
        base_sha="base",
        title="risky",
        body="",
        author="dev",
        diff=risky_diff,
        files=["src/service.py"],
    )
    clients = {
        "security_reviewer": ScriptedLLM([[]]),
        "correctness_reviewer": ScriptedLLM([[]]),
        "test_reviewer": ScriptedLLM([[]]),
        "skeptic": ScriptedLLM([]),
    }
    thread_id = "acme/app#6@head-6"

    async def resume_twice():
        async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
            await saver.setup()
            graph = build_graph(checkpointer=saver, clients=clients)
            first = await graph.ainvoke(
                {
                    "pr": pr,
                    "repo_path": str(tmp_path),
                    "run_id": "dismiss-run",
                    "ci_status": "missing",
                    "incomplete": False,
                },
                config={"configurable": {"thread_id": thread_id}},
            )
            assert first["decision"].outcome == "needs_human"
            dismissed = await human_gate.resume_review(
                graph, thread_id, "/mergeguard dismiss F-1 false alarm", "reviewer"
            )
            assert dismissed["decision"].outcome == "needs_human"
            assert "__interrupt__" in dismissed
            approved = await human_gate.resume_review(
                graph, thread_id, "/mergeguard approve", "reviewer"
            )
            return approved

    result = asyncio.run(resume_twice())
    assert result["decision"].outcome == "pass"
    assert result["decision_findings"] == []
