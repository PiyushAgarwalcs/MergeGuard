# Tests that dismissing a finding can re-interrupt before final approval.

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from mergeguard import storage
from mergeguard.checks import human_gate
from mergeguard.graph import build_graph
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import PullRequest
from mergeguard.settings import settings


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
