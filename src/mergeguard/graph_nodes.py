# mergeguard.graph_nodes
# Implements context, scan, verification, skeptic, judge, and report nodes.

from __future__ import annotations

from typing import Any, cast

from mergeguard.agents import reporter
from mergeguard.agents import skeptic as skeptic_agent
from mergeguard.checks import judge, merge_findings, rule_scan
from mergeguard.checks.verify_findings import verify_findings
from mergeguard.graph_state import GraphState
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import (
    Decision,
    Finding,
    ReviewContext,
    ReviewState,
    Severity,
    SkepticVerdict,
)


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
