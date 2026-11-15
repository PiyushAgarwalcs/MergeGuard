# Wires reviewers and deterministic checks into the LangGraph review flow.
# Ablation variants omit one planned component while preserving safe decisions.

from __future__ import annotations

import asyncio
import operator
from collections.abc import Callable
from functools import partial
from typing import Annotated, Any, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from mergeguard.agents import (
    correctness_reviewer,
    reporter,
    security_reviewer,
    single_reviewer,
    test_reviewer,
)
from mergeguard.agents import skeptic as skeptic_agent
from mergeguard.checks import collect_context, human_gate, judge, merge_findings, rule_scan
from mergeguard.checks.verify_findings import verify_findings
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import (
    Approval,
    Decision,
    Finding,
    PullRequest,
    Rejection,
    ReviewContext,
    ReviewState,
    Severity,
    SkepticVerdict,
)
from mergeguard.settings import settings

VARIANTS = {"full", "single_agent", "no_skeptic", "no_verifier", "no_context", "no_rules"}


class GraphState(TypedDict, total=False):
    """State channels used by the graph, including fan-out reducers."""

    pr: PullRequest
    repo_path: str
    run_id: str
    ci_status: str
    reviewable: bool
    context: ReviewContext
    findings: Annotated[list[Finding], operator.add]
    merged_findings: list[Finding]
    verified_findings: list[Finding]
    decision_findings: list[Finding]
    dismissed_findings: list[Finding]
    rejected: list[Rejection]
    verdicts: list[SkepticVerdict]
    incomplete: Annotated[bool, operator.or_]
    decision: Decision
    approval: Approval | None
    report: str


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


def _after_context(state: GraphState) -> str:
    """Skip model nodes for an empty or missing diff."""
    pr = state.get("pr")
    return (
        "review" if state.get("reviewable", True) and pr is not None and bool(pr.diff) else "empty"
    )


def _scan_rules(state: GraphState, *, variant: str) -> dict[str, list[Finding]]:
    """Run deterministic rules unless the no-rules ablation is active."""
    if variant == "no_rules":
        return {"findings": []}
    return rule_scan.run(cast(ReviewState, state))


def _merge(state: GraphState) -> dict[str, list[Finding]]:
    """Merge duplicate raw findings and assign stable ids."""
    return {"merged_findings": merge_findings.merge_findings(state.get("findings", []))}


def _verify(state: GraphState, *, variant: str) -> dict[str, Any]:
    """Verify model findings, or pass them through in the no-verifier variant."""
    findings = state.get("merged_findings", [])
    if variant == "no_verifier":
        return {"verified_findings": findings, "rejected": []}
    pr = state.get("pr")
    if pr is None:
        return {"verified_findings": [], "rejected": []}
    valid, rejected = verify_findings(findings, pr.diff, state.get("context"))
    return {"verified_findings": valid, "rejected": rejected}


def _skeptic(
    state: GraphState,
    *,
    variant: str,
    client: ScriptedLLM | None,
) -> dict[str, Any]:
    """Apply skeptic verdicts and preserve safe candidates for the judge."""
    verified = state.get("verified_findings", [])
    if variant == "no_skeptic":
        verdicts: list[SkepticVerdict] = []
        incomplete = False
    else:
        pr = state.get("pr")
        if pr is None:
            return {"decision_findings": verified, "verdicts": [], "incomplete": True}
        result = skeptic_agent.review_verified_findings(
            verified,
            pr.diff,
            state.get("context", ReviewContext(ci_status="missing")),
            run_id=state.get("run_id"),
            client=client,
        )
        verdicts = result["verdicts"]
        incomplete = not result["complete"]
    by_id = {verdict.finding_id: verdict.verdict for verdict in verdicts}
    active: list[Finding] = []
    dismissed: list[Finding] = []
    for finding in verified:
        verdict = by_id.get(finding.id)
        if verdict == "refuted":
            dismissed.append(finding)
            continue
        if (
            finding.source.value != "rule"
            and finding.severity == Severity.CRITICAL
            and verdict != "upheld"
        ):
            finding = finding.model_copy(update={"severity": Severity.HIGH})
        active.append(finding)
    return {
        "decision_findings": active,
        "dismissed_findings": dismissed,
        "verdicts": verdicts,
        "incomplete": incomplete,
    }


def _judge(state: GraphState) -> dict[str, Decision]:
    """Apply the deterministic decision table to active verified findings."""
    return {
        "decision": judge.judge_run(
            {
                "pr": state.get("pr"),
                "context": state.get("context"),
                "findings": state.get("decision_findings", []),
                "complete": not state.get("incomplete", False),
            }
        )["decision"]
    }


def _after_judge(state: GraphState) -> str:
    """Route pass decisions directly to the report and others through the gate."""
    decision = state.get("decision")
    return "report" if decision is not None and decision.outcome == "pass" else "human"


def _report(state: GraphState) -> dict[str, str]:
    """Render only active verified findings with the final decision."""
    decision = state.get("decision")
    if decision is None:
        return {
            "report": "## MergeGuard review\n\nReview is incomplete; no decision was produced.\n"
        }
    return reporter.run(
        {
            "findings": state.get("decision_findings", []),
            "decision": decision,
        }
    )
