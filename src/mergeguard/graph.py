# Wires reviewers and deterministic checks into the LangGraph review flow.
# Ablation variants omit one planned component while preserving safe decisions.

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from mergeguard.agents import (
    correctness_reviewer,
    security_reviewer,
    single_reviewer,
    test_reviewer,
)
from mergeguard.checks import collect_context, human_gate
from mergeguard.graph_nodes import (
    _after_context,
    _after_judge,
    _judge,
    _merge,
    _report,
    _scan_rules,
    _skeptic,
    _verify,
)
from mergeguard.graph_state import GraphState
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import ReviewContext, ReviewState
from mergeguard.settings import settings

VARIANTS = {"full", "single_agent", "no_skeptic", "no_verifier", "no_context", "no_rules"}


AgentRunner = Callable[..., dict[str, Any]]


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    variant: str = "full",
    clients: dict[str, ScriptedLLM] | None = None,
) -> Any:
    """Build and compile the full review flow or one requested ablation."""
    if variant not in VARIANTS:
        raise ValueError(f"Unknown graph variant {variant!r}; choose from {sorted(VARIANTS)}.")
    scripted_clients = clients or {}
    builder = StateGraph(GraphState)
    builder.add_node("collect_context", partial(_collect_context, variant=variant))
    builder.add_node("rule_scan", partial(_scan_rules, variant=variant))
    builder.add_node("merge_findings", _merge)
    builder.add_node("verify_findings", partial(_verify, variant=variant))
    builder.add_node(
        "skeptic", partial(_skeptic, variant=variant, client=scripted_clients.get("skeptic"))
    )
    builder.add_node("judge", _judge)
    builder.add_node("human_gate", human_gate.run)
    builder.add_node("reporter", _report)

    if variant == "single_agent":
        _add_agent_node(builder, "single_reviewer", single_reviewer.run, scripted_clients)
        reviewers = ["single_reviewer"]
    else:
        reviewer_specs = [
            ("security_reviewer", security_reviewer.run),
            ("correctness_reviewer", correctness_reviewer.run),
            ("test_reviewer", test_reviewer.run),
        ]
        reviewers = []
        for name, runner in reviewer_specs:
            _add_agent_node(builder, name, runner, scripted_clients)
            reviewers.append(name)

    builder.add_edge(START, "collect_context")
    builder.add_conditional_edges(
        "collect_context", _after_context, {"review": "rule_scan", "empty": "merge_findings"}
    )
    for reviewer in reviewers:
        builder.add_edge("rule_scan", reviewer)
    builder.add_edge(reviewers, "merge_findings")
    builder.add_edge("merge_findings", "verify_findings")
    builder.add_edge("verify_findings", "skeptic")
    builder.add_edge("skeptic", "judge")
    builder.add_conditional_edges(
        "judge",
        _after_judge,
        {"report": "reporter", "human": "human_gate"},
    )
    builder.add_edge("human_gate", "reporter")
    builder.add_edge("reporter", END)
    return builder.compile(checkpointer=checkpointer)


def _add_agent_node(
    builder: StateGraph,
    name: str,
    runner: AgentRunner,
    clients: dict[str, ScriptedLLM],
) -> None:
    """Register one asynchronous LLM node with its timeout and one retry."""
    builder.add_node(
        name,
        _agent_node(runner, clients.get(name)),
        timeout=settings.AGENT_TIMEOUT_SECONDS,
        retry_policy=RetryPolicy(
            initial_interval=0.25,
            backoff_factor=2.0,
            max_interval=0.25,
            max_attempts=2,
            jitter=False,
        ),
        error_handler=_agent_timeout,
    )


def _agent_node(runner: AgentRunner, client: ScriptedLLM | None) -> Callable[..., Any]:
    """Create an async graph node for one sync reviewer implementation."""

    async def execute(state: GraphState) -> dict[str, Any]:
        return await _run_agent(state, runner=runner, client=client)

    return execute


async def _run_agent(
    state: GraphState,
    *,
    runner: AgentRunner,
    client: ScriptedLLM | None,
) -> dict[str, Any]:
    """Run a synchronous model-backed step in a cancellable worker thread."""
    result = await asyncio.to_thread(runner, state, client=client)
    return {
        "findings": result.get("findings", []),
        "incomplete": not bool(result.get("complete", True)),
    }


def _agent_timeout(state: GraphState) -> dict[str, Any]:
    """Keep a timed-out reviewer visible as an incomplete, empty result."""
    del state
    return {"findings": [], "incomplete": True}


def _collect_context(state: GraphState, *, variant: str) -> dict[str, Any]:
    """Build context or return the empty context required by an ablation."""
    pr = state.get("pr")
    if pr is None or not pr.diff:
        return {"context": ReviewContext(ci_status="missing"), "incomplete": True}
    if len(pr.diff.splitlines()) > settings.MAX_DIFF_LINES:
        return {
            "context": ReviewContext(ci_status="missing"),
            "incomplete": True,
            "reviewable": False,
        }
    if variant == "no_context":
        return {"context": ReviewContext(ci_status="missing")}
    return collect_context.run(cast(ReviewState, state))
