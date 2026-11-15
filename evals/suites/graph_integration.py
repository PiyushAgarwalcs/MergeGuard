# L3 integration scenarios use the production graph with a scripted local model.

from __future__ import annotations

import asyncio
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from evals.config import EvalConfig
from evals.results import SuiteCaseResult, SuiteResult
from mergeguard.graph import build_graph
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import PullRequest
from mergeguard.settings import settings

DIFF = """diff --git a/src/worker.py b/src/worker.py
--- a/src/worker.py
+++ b/src/worker.py
@@ -1 +1 @@
+value = load()
"""


def run(config: EvalConfig) -> SuiteResult:
    """Run graph routing and fail-closed reviewer integration scenarios."""
    del config
    previous_mode = settings.LLM_MODE
    settings.LLM_MODE = "record"
    try:
        passed = _invoke("passing", [[]])
        paused = _invoke("missing", [[]])
        malformed = _invoke("passing", ["not json", "still not json"])
        timeout = _invoke("passing", [TimeoutError("fixture timeout")])
        other_reviewer = _invoke("passing", [[]], correctness=[RuntimeError("fixture failure")])
    finally:
        settings.LLM_MODE = previous_mode
    outcomes = {
        "pass_route": passed["decision"].outcome == "pass" and "report" in passed,
        "human_interrupt": paused["decision"].outcome == "needs_human"
        and "__interrupt__" in paused,
        "malformed_output_fails_closed": _needs_human_incomplete(malformed),
        "model_timeout_fails_closed": _needs_human_incomplete(timeout),
        "one_reviewer_failure_fails_closed": _needs_human_incomplete(other_reviewer),
    }
    results = tuple(
        SuiteCaseResult(
            case_id=name,
            repeat=1,
            passed=passed_case,
            expected={"safe_routing": True},
            actual={"safe_routing": passed_case},
            metrics={"mode": "scripted"},
        )
        for name, passed_case in outcomes.items()
    )
    return SuiteResult(
        layer="integration",
        dataset_version="graph-integration-v1",
        repeats=1,
        metrics={
            **{name: float(value) for name, value in outcomes.items()},
            "safe_route_rate": sum(outcomes.values()) / len(outcomes),
            "reviewer_mode": "scripted",
        },
        cases=results,
        prompt_versions={"graph": "phase-7"},
        model_config={"mode": "scripted", "split": "integration"},
    )


def _invoke(
    ci_status: str,
    security: list[Any],
    *,
    correctness: list[Any] | None = None,
) -> dict[str, Any]:
    """Invoke the production graph using isolated scripted reviewer clients."""
    clients = {
        "security_reviewer": ScriptedLLM(security),
        "correctness_reviewer": ScriptedLLM(correctness or [[]]),
        "test_reviewer": ScriptedLLM([[]]),
        "skeptic": ScriptedLLM([]),
    }
    graph = build_graph(checkpointer=InMemorySaver(), clients=clients)
    pr = PullRequest(
        repo="integration/repository",
        number=9,
        head_sha=f"integration-{ci_status}",
        base_sha="integration-base",
        title="Integration test",
        body="",
        author="test-user",
        diff=DIFF,
        files=["src/worker.py"],
    )
    return asyncio.run(
        graph.ainvoke(
            {
                "pr": pr,
                "repo_path": ".",
                "run_id": f"integration-{ci_status}",
                "ci_status": ci_status,
                "incomplete": False,
            },
            config={"configurable": {"thread_id": f"integration#{ci_status}"}},
        )
    )


def _needs_human_incomplete(result: dict[str, Any]) -> bool:
    """Confirm a failed model run cannot be mistaken for a completed pass."""
    decision = result["decision"]
    return decision.outcome == "needs_human" and not decision.complete
