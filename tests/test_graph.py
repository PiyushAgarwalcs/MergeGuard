# Tests graph control flow with a SQLite saver and queued reviewer responses.
# Every graph test uses scripted model calls and an isolated SQLite database.

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from mergeguard import storage
from mergeguard.graph import VARIANTS, build_graph
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import PullRequest
from mergeguard.settings import settings

DIFF = """diff --git a/src/service.py b/src/service.py
--- a/src/service.py
+++ b/src/service.py
@@ -1 +1,2 @@
 existing()
+return new_value
"""


@pytest.fixture
def isolated_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Use a temporary checkpoint/event database and scripted live calls."""
    database = tmp_path / "graph.db"
    monkeypatch.setattr(storage, "DATABASE_PATH", str(database))
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    return database


def _pr(diff: str = DIFF) -> PullRequest:
    return PullRequest(
        repo="example/repo",
        number=4,
        head_sha="head-4",
        base_sha="base-4",
        title="Change behavior",
        body="",
        author="developer",
        diff=diff,
        files=["src/service.py"] if diff else [],
    )


def _clients(
    *, security: list[object] | None = None, variant: str = "full"
) -> dict[str, ScriptedLLM]:
    if variant == "single_agent":
        return {"single_reviewer": ScriptedLLM(security or [[]])}
    return {
        "security_reviewer": ScriptedLLM(security or [[]]),
        "correctness_reviewer": ScriptedLLM([[]]),
        "test_reviewer": ScriptedLLM([[]]),
        "skeptic": ScriptedLLM([]),
    }


def _invoke(
    database: Path,
    *,
    variant: str = "full",
    ci_status: str = "passing",
    diff: str = DIFF,
    security=None,
):
    async def invoke_graph():
        async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
            await saver.setup()
            graph = build_graph(
                saver, variant=variant, clients=_clients(security=security, variant=variant)
            )
            return await graph.ainvoke(
                {
                    "pr": _pr(diff),
                    "repo_path": str(database.parent),
                    "run_id": f"graph-{variant}",
                    "ci_status": ci_status,
                    "incomplete": False,
                },
                config={
                    "configurable": {"thread_id": f"repo#4@{variant}-{ci_status}-{bool(diff)}"}
                },
            )

    return asyncio.run(invoke_graph())


def test_graph_routes_pass_and_human_decisions(isolated_graph: Path) -> None:
    """Take both conditional edges after judge and preserve the decision."""
    passing = _invoke(isolated_graph, ci_status="passing")
    needs_human = _invoke(isolated_graph, ci_status="missing")

    assert passing["decision"].outcome == "pass"
    assert passing["report"].startswith("## MergeGuard review")
    assert needs_human["decision"].outcome == "needs_human"
    assert needs_human["approval"] is None


def test_graph_empty_diff_skips_reviewers(isolated_graph: Path) -> None:
    """Route an empty diff to a visible incomplete decision without model calls."""
    clients = _clients()

    async def invoke_empty():
        graph = build_graph(clients=clients)
        return await graph.ainvoke(
            {"pr": _pr(""), "incomplete": False},
        )

    result = asyncio.run(invoke_empty())

    assert result["decision"].outcome == "needs_human"
    assert result["decision"].complete is False
    assert all(client.calls == 0 for client in clients.values())


def test_graph_failed_reviewer_keeps_decision_incomplete(isolated_graph: Path) -> None:
    """Continue to judge when one reviewer fails after its validation retry."""
    result = _invoke(isolated_graph, security=["not json", "still not json"])

    assert result["decision"].outcome == "needs_human"
    assert result["decision"].complete is False


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_graph_supports_each_ablation(isolated_graph: Path, variant: str) -> None:
    """Compile and execute each planned variant with the scripted transport."""
    result = _invoke(isolated_graph, variant=variant)

    assert result["decision"].outcome in {"pass", "needs_human", "block"}
    assert result["report"].startswith("## MergeGuard review")
