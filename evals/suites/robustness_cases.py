# Executes injection variants and unusual diff inputs through the production graph.
# Scripted model clients keep the per-commit version deterministic and offline.

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from mergeguard.checks.diff_parser import parse_diff
from mergeguard.graph import build_graph
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import PullRequest


def review_diff(
    diff: str,
    *,
    title: str = "Robustness case",
    body: str = "",
    scripted: bool = True,
) -> dict[str, Any]:
    """Run one synthetic PR through the actual graph and return its final state."""
    head = hashlib.sha256(diff.encode("utf-8", errors="replace")).hexdigest()
    files = sorted({hunk.file for hunk in parse_diff(diff)})
    pr = PullRequest(
        repo="robustness/fixture",
        number=1,
        head_sha=head,
        base_sha="robustness-base",
        title=title,
        body=body,
        author="fixture-author",
        diff=diff,
        files=files,
    )
    clients = None
    if scripted:
        clients = {
            name: ScriptedLLM([[]])
            for name in ("security_reviewer", "correctness_reviewer", "test_reviewer")
        }
        clients["skeptic"] = ScriptedLLM([])
    graph = build_graph(checkpointer=InMemorySaver(), clients=clients)
    return asyncio.run(
        graph.ainvoke(
            {
                "pr": pr,
                "repo_path": ".",
                "run_id": f"robustness-{head[:12]}",
                "ci_status": "missing",
                "incomplete": False,
            },
            config={"configurable": {"thread_id": f"robustness-{head}"}},
        )
    )


def without_injection(diff: str, marker: str) -> str:
    """Remove only the wrapper comment while retaining the underlying code change."""
    return (
        diff if not marker else "\n".join(line for line in diff.splitlines() if marker not in line)
    )


def visible_output(result: dict[str, Any]) -> str:
    """Serialize publishable review fields without the source diff or PR metadata."""
    payload = {
        "decision": result.get("decision"),
        "report": result.get("report", ""),
        "findings": result.get("decision_findings", []),
        "interrupt": result.get("__interrupt__", []),
    }
    return str(payload)
