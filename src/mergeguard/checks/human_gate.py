# Parses approver commands, records decisions and pauses/resumes graph runs safely.

from __future__ import annotations

from typing import Any, cast

from langgraph.types import Command, interrupt

from mergeguard.checks import judge
from mergeguard.checks.human_gate_policy import (
    ApprovalRejected,
    GateCommand,
    authorize_command,
    load_approvers,
    parse_command,
)
from mergeguard.models import Approval, Decision, Finding, ReviewState
from mergeguard.storage import insert_event, insert_feedback


def run(state: ReviewState) -> dict[str, Any]:
    """Interrupt for an explicit human command and apply the validated approval."""
    current = dict(state)
    decision = cast(Decision | None, current.get("decision"))
    if decision is None or decision.outcome == "pass":
        return {"approval": None}
    if current.get("pr") is None:
        return {"approval": None, "incomplete": True}
    all_updates: dict[str, Any] = {}
    while True:
        decision = cast(Decision, current["decision"])
        pr = cast(Any, current["pr"])
        findings = cast(list[Finding], current.get("decision_findings", []))
        resume = interrupt(
            {
                "kind": "approval_required",
                "run_id": current.get("run_id", ""),
                "head_sha": pr.head_sha,
                "outcome": decision.outcome,
                "reasons": decision.reasons,
                "finding_ids": [finding.id for finding in findings],
            }
        )
        payload = resume.get("approval", resume) if isinstance(resume, dict) else resume
        approval = Approval.model_validate(payload)
        _validate_approval(approval, cast(ReviewState, current))
        updated = _apply_approval(approval, cast(ReviewState, current))
        all_updates.update(updated)
        current.update(updated)
        updated_decision = cast(Decision, current["decision"])
        if updated_decision.outcome == "pass":
            return all_updates


def record_command(
    text: str,
    by_user: str,
    state: ReviewState,
) -> Approval:
    """Parse, authorize, and persist a command before graph resumption."""
    pr = state.get("pr")
    decision = state.get("decision")
    if pr is None or decision is None:
        raise ApprovalRejected("The review checkpoint has no pull request decision.")
    command = parse_command(text)
    findings = cast(list[Finding], state.get("decision_findings", []))
    approval = authorize_command(
        command,
        by_user,
        load_approvers(state.get("repo_path", ".")),
        head_sha=pr.head_sha,
        decision=decision,
        findings=findings,
    )
    run_id = state.get("run_id", "unknown-run")
    insert_feedback(
        run_id,
        approval.finding_id or "",
        approval.kind,
        approval.by_user,
        approval.reason,
    )
    insert_event(
        run_id,
        "human_gate",
        "approval_action",
        {
            "kind": approval.kind,
            "by_user": approval.by_user,
            "reason": approval.reason,
            "head_sha": approval.head_sha,
            "finding_id": approval.finding_id,
        },
    )
    return approval


async def resume_review(graph: Any, thread_id: str, text: str, by_user: str) -> dict[str, Any]:
    """Authorize and persist a comment command, then resume its paused graph thread."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise ApprovalRejected("No saved review checkpoint exists for this thread.")
    approval = record_command(text, by_user, cast(ReviewState, snapshot.values))
    resumed = await graph.ainvoke(
        Command(resume={"approval": approval.model_dump(mode="json")}), config=config
    )
    return cast(dict[str, Any], resumed)


def _validate_approval(approval: Approval, state: ReviewState) -> None:
    """Recheck resumed payloads so direct checkpoint resumes cannot bypass policy."""
    pr = state.get("pr")
    decision = state.get("decision")
    if pr is None or decision is None:
        raise ApprovalRejected("The review checkpoint is missing its decision or head SHA.")
    if approval.head_sha != pr.head_sha:
        raise ApprovalRejected("Approval belongs to a stale pull request head SHA.")
    command = GateCommand(approval.kind, approval.reason, approval.finding_id)
    authorize_command(
        command,
        approval.by_user,
        load_approvers(state.get("repo_path", ".")),
        head_sha=pr.head_sha,
        decision=decision,
        findings=cast(list[Finding], state.get("decision_findings", [])),
    )


def _apply_approval(approval: Approval, state: ReviewState) -> dict[str, Any]:
    """Apply an accepted command to the final decision and reporter inputs."""
    decision = state.get("decision")
    if decision is None:
        raise ApprovalRejected("The review decision is missing.")
    if approval.kind in {"approve", "override"}:
        reason = f"Decision cleared by {approval.by_user}: {approval.reason or 'approved'}"
        return {
            "approval": approval,
            "decision": decision.model_copy(
                update={"outcome": "pass", "reasons": [reason], "complete": True}
            ),
        }
    findings = cast(list[Finding], state.get("decision_findings", []))
    remaining = [finding for finding in findings if finding.id != approval.finding_id]
    updated_state = dict(state)
    updated_state["findings"] = remaining
    updated_state["decision_findings"] = remaining
    updated_state["complete"] = decision.complete
    judged = judge.judge_run(updated_state)
    return {"approval": approval, "decision_findings": remaining, "decision": judged["decision"]}


__all__ = [
    "ApprovalRejected",
    "GateCommand",
    "authorize_command",
    "load_approvers",
    "parse_command",
    "record_command",
    "resume_review",
    "run",
]
